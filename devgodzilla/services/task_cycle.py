from __future__ import annotations

import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from devgodzilla.api import schemas
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import StepRun, StepStatus
from devgodzilla.qa.gates.interface import GateResult, GateVerdict
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.execution import ExecutionService
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.quality import QAResult, QAVerdict, QualityService
from devgodzilla.services.spec_to_protocol import SpecToProtocolService
from devgodzilla.services.specification import SpecificationService
from devgodzilla.services.workspace_paths import (
    WorkspacePathError,
    resolve_protocol_root,
    resolve_workspace_root,
)

logger = get_logger(__name__)


class TaskCycleError(RuntimeError):
    """Raised when a task-cycle action cannot be completed safely."""


class TaskCycleService(Service):
    RUNTIME_KEY = "task_cycle"
    STATUS_QUEUED = "queued"
    STATUS_CONTEXT_READY = "context_ready"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_AWAITING_REVIEW = "awaiting_review"
    STATUS_NEEDS_REWORK = "needs_rework"
    STATUS_READY_FOR_PR = "ready_for_pr"
    STATUS_PR_READY = "pr_ready"
    STATUS_BLOCKED = "blocked"

    def __init__(self, context: ServiceContext, db) -> None:
        super().__init__(context)
        self.db = db

    def list_work_items(
        self,
        project_id: int,
        *,
        protocol_run_id: Optional[int] = None,
    ) -> List[schemas.WorkItemOut]:
        if protocol_run_id is not None:
            run = self.db.get_protocol_run(protocol_run_id)
            if run.project_id != project_id:
                raise TaskCycleError("Protocol run does not belong to the requested project")
            runs = [run]
        else:
            runs = [run for run in self.db.list_protocol_runs(project_id) if self._is_task_cycle_run(run)]

        items: List[schemas.WorkItemOut] = []
        for run in runs:
            for step in self.db.list_step_runs(run.id):
                items.append(self.get_work_item(step.id))
        return sorted(items, key=lambda item: (item.protocol_run_id, item.id))

    def get_work_item(self, step_run_id: int) -> schemas.WorkItemOut:
        step, run, project = self._load_work_item(step_run_id)
        state = self._task_cycle_state(step, project)
        blocking_clarifications = self._blocking_clarifications(project.id, run.id, step.id)
        return schemas.WorkItemOut(
            id=step.id,
            project_id=project.id,
            protocol_run_id=run.id,
            title=step.step_name,
            status=str(state["status"]),
            context_status=str(state["context_status"]),
            review_status=str(state["review_status"]),
            qa_status=str(state["qa_status"]),
            owner_agent=self._string_or_none(state.get("owner_agent")) or step.assigned_agent,
            helper_agents=self._string_list(state.get("helper_agents")),
            task_dir=self._string_or_none(state.get("task_dir")),
            artifact_refs=schemas.WorkItemArtifactRefsOut(**self._artifact_refs(project, step)),
            depends_on=list(step.depends_on or []),
            pr_ready=bool(state.get("pr_ready", False)),
            blocking_clarifications=blocking_clarifications,
            blocking_policy_findings=int(state.get("blocking_policy_findings", 0) or 0),
            iteration_count=int(state.get("iteration_count", 0) or 0),
            max_iterations=int(state.get("max_iterations", self.config.task_cycle_max_iterations) or self.config.task_cycle_max_iterations),
            summary=step.summary,
        )

    def start_brownfield_run(
        self,
        project_id: int,
        request: schemas.BrownfieldRunRequest,
    ) -> schemas.BrownfieldRunOut:
        project = self.db.get_project(project_id)
        if not project.local_path:
            raise TaskCycleError("Project has no local path")
        resolved_owner_agent = self._resolve_owner_agent(project.id, request.owner_agent)

        spec_service = SpecificationService(self.context, self.db)
        protocol_service = SpecToProtocolService(self.context, self.db)

        specify = spec_service.run_specify(
            project.local_path,
            request.feature_request,
            feature_name=request.feature_name,
            base_branch=request.branch,
            project_id=project_id,
        )
        if not specify.success or not specify.spec_path:
            raise TaskCycleError(specify.error or "Spec generation failed")

        plan = spec_service.run_plan(
            project.local_path,
            specify.spec_path,
            spec_run_id=specify.spec_run_id,
            project_id=project_id,
        )
        if not plan.success or not plan.plan_path:
            raise TaskCycleError(plan.error or "Plan generation failed")

        tasks = spec_service.run_tasks(
            project.local_path,
            plan.plan_path,
            spec_run_id=specify.spec_run_id,
            project_id=project_id,
        )
        if not tasks.success or not tasks.tasks_path:
            raise TaskCycleError(tasks.error or "Task generation failed")

        warnings: List[str] = []
        protocol_out = None
        work_items: List[schemas.WorkItemOut] = []
        next_work_item_id: Optional[int] = None

        if request.output_mode in {"task_cycle", "protocol"}:
            protocol = protocol_service.create_protocol_from_spec(
                project_id=project_id,
                spec_path=specify.spec_path,
                tasks_path=tasks.tasks_path,
                protocol_name=request.protocol_name,
                spec_run_id=specify.spec_run_id,
                overwrite=request.overwrite_protocol,
            )
            if not protocol.success or not protocol.protocol_run_id:
                raise TaskCycleError(protocol.error or "Protocol creation failed")
            warnings.extend(protocol.warnings)
            protocol_run = self.db.get_protocol_run(protocol.protocol_run_id)
            protocol_metadata = dict(protocol_run.speckit_metadata or {})
            protocol_metadata.update(
                {
                    "task_cycle": request.output_mode == "task_cycle",
                    "brownfield_output_mode": request.output_mode,
                    "spec_run_id": specify.spec_run_id,
                    "spec_path": specify.spec_path,
                    "plan_path": plan.plan_path,
                    "tasks_path": tasks.tasks_path,
                }
            )
            protocol_run = self.db.update_protocol_windmill(
                protocol.protocol_run_id,
                speckit_metadata=protocol_metadata,
            )
            protocol_out = schemas.ProtocolOut.model_validate(protocol_run)
            self._seed_task_cycle_metadata(
                protocol.protocol_run_id,
                owner_agent=resolved_owner_agent,
                helper_agents=request.helper_agents if (request.allow_helper_agents or request.helper_agents) else [],
            )

            # Auto-advance the first pending step.
            # Without this, protocol steps created by brownfield run stay in
            # "pending" forever because nothing dispatches them.
            if True:
                try:
                    steps = self.db.list_step_runs(protocol.protocol_run_id)
                    completed_ids = {s.id for s in steps if s.status == StepStatus.COMPLETED}
                    pending = [s for s in steps if s.status == StepStatus.PENDING]
                    first_runnable = next(
                        (
                            s
                            for s in sorted(pending, key=lambda s: (s.priority or 999))
                            if all(d in completed_ids for d in (s.depends_on or []))
                        ),
                        None,
                    )
                    if first_runnable is not None:
                        ExecutionService(self.context, self.db).execute_step(first_runnable.id)
                        logger.info(
                            "brownfield_auto_advanced_step",
                            extra={
                                "protocol_run_id": protocol.protocol_run_id,
                                "step_run_id": first_runnable.id,
                                "step_name": first_runnable.step_name,
                            },
                        )
                except Exception as exc:
                    logger.warning(
                        "brownfield_auto_advance_failed",
                        extra={
                            "protocol_run_id": protocol.protocol_run_id,
                            "error": str(exc),
                        },
                    )

            work_items = self.list_work_items(project_id, protocol_run_id=protocol.protocol_run_id)
            next_work_item_id = next((item.id for item in work_items if not item.pr_ready), None)

        return schemas.BrownfieldRunOut(
            success=True,
            project_id=project_id,
            output_mode=request.output_mode,
            spec_run_id=specify.spec_run_id,
            spec_path=specify.spec_path,
            plan_path=plan.plan_path,
            tasks_path=tasks.tasks_path,
            protocol=protocol_out,
            work_items=work_items,
            next_work_item_id=next_work_item_id,
            warnings=warnings,
        )

    def build_context(self, step_run_id: int, *, refresh: bool = False) -> schemas.WorkItemOut:
        step, run, project = self._load_work_item(step_run_id)
        task_dir = self._task_dir(project, step)
        refs = self._artifact_refs(project, step)
        context_json = Path(refs["context_pack_json"])

        if context_json.exists() and not refresh:
            state = self._task_cycle_state(step, project)
            state["context_status"] = "ready"
            state["status"] = state["status"] if state["status"] != self.STATUS_QUEUED else self.STATUS_CONTEXT_READY
            self._persist_task_cycle_state(step, state)
            return self.get_work_item(step.id)

        workspace_root = self._workspace_root(run, project)
        protocol_root = self._protocol_root(run, workspace_root)
        step_prompt_path = protocol_root / f"{step.step_name}.md"
        plan_path = protocol_root / "plan.md"
        step_text = step_prompt_path.read_text(encoding="utf-8") if step_prompt_path.exists() else (step.summary or "")
        plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""

        manifests = self._discover_manifest_files(workspace_root)
        style_guides = self._discover_style_guides(workspace_root)
        path_refs = self._extract_path_references(step_text, plan_text)
        code_refs = self._discover_code_files(workspace_root, step, path_refs)
        required_files = self._curate_required_files(
            workspace_root,
            protocol_root,
            step_prompt_path,
            plan_path,
            path_refs,
            code_refs,
        )
        entry_points = self._entry_points(workspace_root, protocol_root, step_prompt_path, plan_path, required_files)
        acceptance_criteria = self._extract_acceptance_criteria(step_text)
        review_focus = acceptance_criteria[:3] if acceptance_criteria else [f"Validate implementation for {step.step_name}"]
        goal = self._extract_goal(step_text, step)
        test_command_specs = self._detect_test_command_specs(workspace_root, required_files)
        test_commands = [str(item["display"]) for item in test_command_specs]
        open_questions = self._context_open_questions(entry_points, required_files, test_commands)
        clarifications = self._ensure_context_clarifications(
            project_id=project.id,
            protocol_run_id=run.id,
            step_run_id=step.id,
            title=step.step_name,
            open_questions=open_questions,
        )

        payload: Dict[str, Any] = {
            "context_version": "1",
            "work_item_id": f"step-{step.id}",
            "project_id": project.id,
            "protocol_run_id": run.id,
            "step_run_id": step.id,
            "title": step.step_name,
            "goal": goal,
            "acceptance_criteria": acceptance_criteria,
            "status": "context_ready",
            "repo_root": str(workspace_root),
            "base_branch": run.base_branch,
            "entry_points": entry_points,
            "required_files": required_files,
            "candidate_files": required_files,
            "code_context_files": code_refs,
            "contracts": [],
            "types": [],
            "schemas": [],
            "manifest_files": manifests,
            "style_guides": style_guides,
            "test_commands": test_commands,
            "test_command_specs": test_command_specs,
            "review_focus": review_focus,
            "risks": self._derive_risks(step, required_files),
            "assumptions": [],
            "open_questions": open_questions,
            "clarification_refs": clarifications,
            "dependencies": list(step.depends_on or []),
            "artifact_refs": refs,
            "generated_at": self._now_iso(),
        }

        task_dir.mkdir(parents=True, exist_ok=True)
        context_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        Path(refs["context_pack_md"]).write_text(self._render_context_markdown(payload), encoding="utf-8")

        state = self._task_cycle_state(step, project)
        state["context_status"] = "needs_clarification" if open_questions else "ready"
        if state["status"] == self.STATUS_QUEUED:
            state["status"] = self.STATUS_CONTEXT_READY
        self._persist_task_cycle_state(step, state)
        return self.get_work_item(step.id)

    def implement(self, step_run_id: int, *, owner_agent: Optional[str] = None) -> schemas.WorkItemOut:
        step, run, project = self._load_work_item(step_run_id)
        state = self._task_cycle_state(step, project)
        resolved_owner_agent = self._resolve_owner_agent(
            project.id,
            owner_agent or self._string_or_none(state.get("owner_agent")) or step.assigned_agent,
        )
        if resolved_owner_agent and resolved_owner_agent != step.assigned_agent:
            self.db.update_step_assigned_agent(step.id, resolved_owner_agent)
            step = self.db.get_step_run(step.id)

        iterations = int(state.get("iteration_count", 0) or 0)
        max_iterations = int(state.get("max_iterations", self.config.task_cycle_max_iterations) or self.config.task_cycle_max_iterations)
        if iterations >= max_iterations:
            state["status"] = self.STATUS_BLOCKED
            state["last_failure_source"] = "iteration_limit"
            self._persist_task_cycle_state(step, state)
            raise TaskCycleError(f"Max task-cycle iterations reached ({max_iterations})")

        state["iteration_count"] = iterations + 1
        state["max_iterations"] = max_iterations
        state["owner_agent"] = resolved_owner_agent or step.assigned_agent or state.get("owner_agent")
        state["status"] = self.STATUS_IN_PROGRESS
        state["review_status"] = "pending"
        state["qa_status"] = "pending"
        state["pr_ready"] = False
        self._persist_task_cycle_state(step, state)

        execution = ExecutionService(self.context, self.db)
        result = execution.execute_step(step.id)
        step = self.db.get_step_run(step.id)
        state = self._task_cycle_state(step, project)

        if not result.success or step.status in (StepStatus.FAILED, StepStatus.TIMEOUT, StepStatus.BLOCKED):
            state["status"] = self.STATUS_NEEDS_REWORK
            state["last_failure_source"] = "implement"
            self._write_rework_pack(
                project=project,
                run=run,
                step=step,
                source="implement",
                findings=[result.error or f"Implementation ended in {step.status}"],
            )
        else:
            # Task-cycle QA is an explicit stage with its own persisted artifacts.
            state["qa_status"] = "pending"
            state["status"] = self.STATUS_AWAITING_REVIEW
            state["last_failure_source"] = None
        self._persist_task_cycle_state(step, state)
        return self.get_work_item(step.id)

    def review(self, step_run_id: int) -> Tuple[schemas.WorkItemOut, schemas.WorkItemReviewOut]:
        step, run, project = self._load_work_item(step_run_id)
        self.build_context(step.id, refresh=False)
        refs = self._artifact_refs(project, step)
        task_dir = Path(refs["task_dir"])
        context_pack = self._read_json(Path(refs["context_pack_json"]))
        blocking_findings: List[str] = []
        warnings: List[str] = []

        step_artifacts_dir = Path(refs["step_artifacts_dir"])
        if not Path(refs["context_pack_json"]).exists():
            blocking_findings.append("Missing context_pack.json")
        if not step_artifacts_dir.exists():
            blocking_findings.append("Missing step artifacts directory")
        if step_artifacts_dir.exists() and not any(step_artifacts_dir.iterdir()):
            warnings.append("Step artifacts directory is empty")
        if step.status in (StepStatus.FAILED, StepStatus.TIMEOUT, StepStatus.BLOCKED):
            blocking_findings.append(f"Step is not in a reviewable state: {step.status}")

        for item in context_pack.get("manifest_files", []):
            path = self._resolve_workspace_path(Path(context_pack["repo_root"]), item.get("path"))
            if path is None or not path.exists():
                warnings.append(f"Referenced manifest missing: {item.get('path')}")
        for item in context_pack.get("style_guides", []):
            path = self._resolve_workspace_path(Path(context_pack["repo_root"]), item.get("path"))
            if path is None or not path.exists():
                warnings.append(f"Referenced style guide missing: {item.get('path')}")
        if not context_pack.get("test_commands"):
            warnings.append("ContextPack does not define test commands")

        blocking_policy_findings = self._evaluate_blocking_policy_findings(step.id, run, project)
        if blocking_policy_findings:
            blocking_findings.append(f"Policy findings require attention ({blocking_policy_findings})")

        verdict = "passed"
        summary = "Review passed"
        if blocking_findings:
            verdict = "failed"
            summary = f"Review failed with {len(blocking_findings)} blocking findings"
        elif warnings:
            verdict = "warning"
            summary = f"Review produced {len(warnings)} warnings"

        report = {
            "work_item_id": step.id,
            "protocol_run_id": run.id,
            "project_id": project.id,
            "verdict": verdict,
            "summary": summary,
            "blocking_findings": blocking_findings,
            "warnings": warnings,
            "checked_at": self._now_iso(),
            "context_pack_json": refs["context_pack_json"],
        }
        task_dir.mkdir(parents=True, exist_ok=True)
        Path(refs["review_report_json"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
        Path(refs["review_report_md"]).write_text(self._render_review_markdown(report), encoding="utf-8")

        state = self._task_cycle_state(step, project)
        state["review_status"] = verdict
        state["blocking_policy_findings"] = blocking_policy_findings
        if verdict == "passed":
            state["status"] = (
                self.STATUS_READY_FOR_PR if state.get("qa_status") == "passed" else self.STATUS_AWAITING_REVIEW
            )
            state["last_failure_source"] = None
        else:
            state["status"] = self.STATUS_NEEDS_REWORK
            state["last_failure_source"] = "review"
            self._write_rework_pack(
                project=project,
                run=run,
                step=step,
                source="review",
                findings=blocking_findings,
                warnings=warnings,
            )
        self._persist_task_cycle_state(step, state)

        return self.get_work_item(step.id), schemas.WorkItemReviewOut(
            verdict=verdict,
            summary=summary,
            blocking_findings=blocking_findings,
            warnings=warnings,
        )

    def qa(self, step_run_id: int, *, gates: Optional[List[str]] = None) -> schemas.WorkItemQAOut:
        step, run, project = self._load_work_item(step_run_id)
        refs = self._artifact_refs(project, step)
        state = self._task_cycle_state(step, project)
        step_artifacts_dir = Path(refs["step_artifacts_dir"])
        context_pack_json = Path(refs["context_pack_json"])
        if not context_pack_json.exists():
            raise TaskCycleError("Build context before running QA")
        if step.status in (StepStatus.FAILED, StepStatus.TIMEOUT, StepStatus.BLOCKED):
            raise TaskCycleError(f"Step is not in a QA-ready state: {step.status}")
        if state.get("review_status") in {"failed", "warning"}:
            raise TaskCycleError("Resolve review findings before running QA")
        if not step_artifacts_dir.exists() or not any(step_artifacts_dir.iterdir()):
            raise TaskCycleError("Implementation artifacts are missing; run Implement successfully before QA")
        gate_map = {
            "lint": __import__("devgodzilla.qa.gates", fromlist=["LintGate"]).LintGate,
            "type": __import__("devgodzilla.qa.gates", fromlist=["TypeGate"]).TypeGate,
            "test": __import__("devgodzilla.qa.gates", fromlist=["TestGate"]).TestGate,
        }

        quality = QualityService(self.context, self.db)
        gates_to_run = None
        if gates is not None:
            unknown = [gate for gate in gates if gate not in gate_map]
            if unknown:
                raise TaskCycleError(f"Unknown QA gates: {', '.join(unknown)}")
            gates_to_run = [gate_map[gate]() for gate in gates]

        # Task-cycle explicit gate selection should stay deterministic.
        # If the caller requested concrete QA gates, do not implicitly re-add prompt QA.
        skip_gates = ["prompt_qa"] if gates is not None else None
        qa_result = quality.run_qa(step.id, gates=gates_to_run, skip_gates=skip_gates)
        task_dir = Path(refs["task_dir"])
        task_dir.mkdir(parents=True, exist_ok=True)
        qa_json_path = Path(refs["test_report_json"])
        qa_md_path = Path(refs["test_report_md"])
        qa_report = self._serialize_qa_report(qa_result)
        qa_json_path.write_text(json.dumps(qa_report, indent=2), encoding="utf-8")
        qa_md_path.write_text(self._render_qa_markdown(qa_report), encoding="utf-8")
        quality.persist_verdict(qa_result, step.id, report_path=qa_md_path)

        qa_out = schemas.QAResultOut(
            verdict=self._map_qa_verdict(qa_result.verdict.value),
            summary=qa_report["summary"],
            gates=[
                schemas.QAGateOut(
                    id=result["id"],
                    name=result["name"],
                    status=result["status"],
                    findings=[
                        schemas.QAFindingOut(
                            severity=finding["severity"],
                            message=finding["message"],
                            file=finding.get("file"),
                            line=finding.get("line"),
                            rule_id=finding.get("rule_id"),
                            suggestion=finding.get("suggestion"),
                        )
                        for finding in result["findings"]
                    ],
                )
                for result in qa_report["gates"]
            ],
        )

        state["qa_status"] = qa_out.verdict
        if qa_out.verdict == "passed":
            state["status"] = self.STATUS_READY_FOR_PR if state.get("review_status") == "passed" else self.STATUS_AWAITING_REVIEW
            state["last_failure_source"] = None
        else:
            state["status"] = self.STATUS_NEEDS_REWORK
            state["last_failure_source"] = "qa"
            findings = [
                finding.message
                for gate in qa_out.gates
                for finding in gate.findings
                if finding.severity in {"error", "warning"}
            ]
            self._write_rework_pack(
                project=project,
                run=run,
                step=step,
                source="qa",
                findings=findings,
                warnings=[],
            )
        self._persist_task_cycle_state(step, state)

        return schemas.WorkItemQAOut(work_item=self.get_work_item(step.id), qa=qa_out)

    def mark_pr_ready(self, step_run_id: int) -> schemas.WorkItemOut:
        step, run, project = self._load_work_item(step_run_id)
        self.build_context(step.id, refresh=False)
        state = self._task_cycle_state(step, project)
        refs = self._artifact_refs(project, step)
        blocking_clarifications = self._blocking_clarifications(project.id, run.id, step.id)
        blocking_policy_findings = self._evaluate_blocking_policy_findings(step.id, run, project)

        required_paths = [
            refs["context_pack_json"],
            refs["review_report_json"],
            refs["test_report_json"],
        ]
        missing = [path for path in required_paths if not Path(path).exists()]
        if missing:
            raise TaskCycleError(f"Missing required artifacts: {', '.join(missing)}")
        if state.get("review_status") != "passed":
            raise TaskCycleError("Review must pass before marking PR-ready")
        if state.get("qa_status") != "passed":
            raise TaskCycleError("QA must pass before marking PR-ready")
        if blocking_clarifications:
            raise TaskCycleError("Blocking clarifications must be resolved before marking PR-ready")
        if blocking_policy_findings:
            raise TaskCycleError("Blocking policy findings must be resolved before marking PR-ready")

        state["pr_ready"] = True
        state["status"] = self.STATUS_PR_READY
        state["blocking_policy_findings"] = blocking_policy_findings
        self._persist_task_cycle_state(step, state)
        return self.get_work_item(step.id)

    def _load_work_item(self, step_run_id: int):
        step = self.db.get_step_run(step_run_id)
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        return step, run, project

    def _task_cycle_state(self, step: StepRun, project) -> Dict[str, Any]:
        runtime_state = dict(step.runtime_state or {})
        current = dict(runtime_state.get(self.RUNTIME_KEY) or {})
        refs = self._artifact_refs(project, step)
        state = {
            "status": current.get("status", self.STATUS_QUEUED),
            "context_status": current.get("context_status", "ready" if Path(refs["context_pack_json"]).exists() else "missing"),
            "review_status": current.get("review_status", "pending"),
            "qa_status": current.get("qa_status", "pending"),
            "pr_ready": bool(current.get("pr_ready", False)),
            "owner_agent": current.get("owner_agent") or step.assigned_agent,
            "helper_agents": self._string_list(current.get("helper_agents")),
            "iteration_count": int(current.get("iteration_count", 0) or 0),
            "max_iterations": int(current.get("max_iterations", self.config.task_cycle_max_iterations) or self.config.task_cycle_max_iterations),
            "task_dir": refs["task_dir"],
            "artifact_refs": refs,
            "blocking_policy_findings": int(current.get("blocking_policy_findings", 0) or 0),
            "last_failure_source": current.get("last_failure_source"),
        }
        return state

    def _is_task_cycle_run(self, run) -> bool:
        metadata = dict(run.speckit_metadata or {})
        if metadata.get("task_cycle") or metadata.get("brownfield_output_mode") == "task_cycle":
            return True
        for step in self.db.list_step_runs(run.id):
            runtime_state = dict(step.runtime_state or {})
            if self.RUNTIME_KEY in runtime_state:
                return True
        return False

    def _persist_task_cycle_state(self, step: StepRun, state: Dict[str, Any]) -> StepRun:
        runtime_state = dict(step.runtime_state or {})
        runtime_state[self.RUNTIME_KEY] = state
        return self.db.update_step_run(step.id, runtime_state=runtime_state)

    def _artifact_refs(self, project, step: StepRun) -> Dict[str, str]:
        task_dir = self._task_dir(project, step)
        refs = {
            "task_dir": str(task_dir),
            "context_pack_json": str(task_dir / "context_pack.json"),
            "context_pack_md": str(task_dir / "context_pack.md"),
            "review_report_json": str(task_dir / "review_report.json"),
            "review_report_md": str(task_dir / "review_report.md"),
            "test_report_json": str(task_dir / "test_report.json"),
            "test_report_md": str(task_dir / "test_report.md"),
            "rework_pack_json": str(task_dir / "rework_pack.json"),
            "step_artifacts_dir": str(self._step_artifacts_dir(step)),
        }
        return refs

    def read_artifact_content(self, step_run_id: int, artifact_key: str, *, max_bytes: int = 200_000) -> schemas.ArtifactContentOut:
        step, _run, project = self._load_work_item(step_run_id)
        refs = self._artifact_refs(project, step)
        if artifact_key not in refs:
            raise TaskCycleError(f"Unknown task-cycle artifact: {artifact_key}")
        path = Path(refs[artifact_key])
        if not path.exists() or not path.is_file():
            raise TaskCycleError(f"Artifact not found: {artifact_key}")

        max_bytes = max(1, min(int(max_bytes), 2_000_000))
        raw = path.read_bytes()
        truncated = len(raw) > max_bytes
        if truncated:
            raw = raw[:max_bytes]

        try:
            content = raw.decode("utf-8")
        except Exception:
            content = raw.decode("utf-8", errors="replace")

        return schemas.ArtifactContentOut(
            id=artifact_key,
            name=path.name,
            type=self._artifact_type_from_name(path.name),
            content=content,
            truncated=truncated,
        )

    def _task_dir(self, project, step: StepRun) -> Path:
        run = self.db.get_protocol_run(step.protocol_run_id)
        workspace_root = self._workspace_root(run, project)
        return workspace_root / ".devgodzilla" / "task-cycle" / "protocols" / str(run.id) / "work-items" / str(step.id)

    def _workspace_root(self, run, project) -> Path:
        try:
            return resolve_workspace_root(run, project)
        except WorkspacePathError as exc:
            raise TaskCycleError(str(exc)) from exc

    def _protocol_root(self, run, workspace_root: Path) -> Path:
        return resolve_protocol_root(run, workspace_root)

    def _step_artifacts_dir(self, step: StepRun) -> Path:
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        protocol_root = self._protocol_root(run, self._workspace_root(run, project))
        return protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"

    def _discover_manifest_files(self, workspace_root: Path) -> List[Dict[str, str]]:
        candidates = (
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "docker-compose.yml",
            "docker-compose.yaml",
        )
        items: List[Dict[str, str]] = []
        for name in candidates:
            path = workspace_root / name
            if path.exists():
                items.append({"path": name, "reason": "Project manifest or tooling definition"})
        return items

    def _discover_style_guides(self, workspace_root: Path) -> List[Dict[str, str]]:
        candidates = (
            "AGENTS.md",
            ".specify/memory/constitution.md",
            ".editorconfig",
        )
        items: List[Dict[str, str]] = []
        for name in candidates:
            path = workspace_root / name
            if path.exists():
                items.append({"path": name, "reason": "Project-specific guidance or coding policy"})
        return items

    def _discover_code_files(self, workspace_root: Path, step: StepRun, path_refs: Iterable[str]) -> List[Dict[str, str]]:
        ranked: List[Tuple[Path, str, int]] = []
        seen: set[Path] = set()
        hints = {token for token in re.split(r"[^a-z0-9]+", f"{step.step_name} {step.summary or ''}".lower()) if len(token) >= 3}
        hints.update(Path(ref).stem.lower() for ref in path_refs if "." in ref)

        for path in self._iter_workspace_files(workspace_root):
            if path in seen:
                continue
            relative = str(path.relative_to(workspace_root)).lower()
            name = path.name.lower()
            score = 0
            for hint in hints:
                if hint and hint in relative:
                    score += 2 if hint in name else 1
            if path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                score += 1
            if "test" in relative:
                score += 1
            if score <= 0:
                continue
            seen.add(path)
            ranked.append((path, "Code-first match for the work item", score))

        ranked.sort(key=lambda item: (-item[2], str(item[0])))
        return [
            {"path": str(path.relative_to(workspace_root)), "reason": reason}
            for path, reason, _score in ranked[:8]
        ]

    def _extract_path_references(self, *texts: str) -> List[str]:
        pattern = re.compile(r"(?P<path>[A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+)")
        refs: List[str] = []
        for text in texts:
            for match in pattern.finditer(text or ""):
                refs.append(match.group("path"))
        return refs

    def _curate_required_files(
        self,
        workspace_root: Path,
        protocol_root: Path,
        step_prompt_path: Path,
        plan_path: Path,
        path_refs: Iterable[str],
        code_refs: Iterable[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        files: List[Tuple[Path, str]] = []
        if step_prompt_path.exists():
            files.append((step_prompt_path, "Task prompt for the work item"))
        if plan_path.exists():
            files.append((plan_path, "Protocol or runtime plan for the work item"))
        for ref in path_refs:
            path = self._resolve_workspace_path(workspace_root, ref)
            if path and path.exists() and path.is_file():
                files.append((path, "File referenced by the task context"))
        for ref in code_refs:
            path = self._resolve_workspace_path(workspace_root, ref.get("path"))
            if path and path.exists() and path.is_file():
                files.append((path, ref.get("reason") or "Code-first context file"))
        curated: List[Dict[str, str]] = []
        seen: set[str] = set()
        for path, reason in files:
            label = self._relative_or_absolute(path, workspace_root, protocol_root)
            if label in seen:
                continue
            seen.add(label)
            curated.append({"path": label, "reason": reason})
        return curated

    def _entry_points(
        self,
        workspace_root: Path,
        protocol_root: Path,
        step_prompt_path: Path,
        plan_path: Path,
        required_files: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        if step_prompt_path.exists():
            items.append({"path": self._relative_or_absolute(step_prompt_path, workspace_root, protocol_root), "reason": "Task prompt entry point"})
        if plan_path.exists():
            items.append({"path": self._relative_or_absolute(plan_path, workspace_root, protocol_root), "reason": "Plan entry point"})
        items.extend(required_files[:4])
        unique: List[Dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            path = item["path"]
            if path in seen:
                continue
            seen.add(path)
            unique.append(item)
        return unique

    def _extract_acceptance_criteria(self, step_text: str) -> List[str]:
        criteria: List[str] = []
        for raw in (step_text or "").splitlines():
            line = raw.strip()
            if line.startswith("- [ ] "):
                criteria.append(line[6:].strip())
            elif line.startswith("- ") and len(criteria) < 5:
                criteria.append(line[2:].strip())
        return criteria[:5]

    def _extract_goal(self, step_text: str, step: StepRun) -> str:
        for raw in (step_text or "").splitlines():
            line = raw.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return step.summary or step.step_name

    def _derive_risks(self, step: StepRun, required_files: List[Dict[str, str]]) -> List[str]:
        risks = [f"Changes may affect files referenced by {step.step_name}"]
        if required_files:
            risks.append(f"Review interactions across {len(required_files)} curated files")
        return risks

    def _detect_test_commands(self, workspace_root: Path, required_files: Optional[List[Dict[str, str]]] = None) -> List[str]:
        return [str(item["display"]) for item in self._detect_test_command_specs(workspace_root, required_files or [])]

    def _detect_test_command_specs(
        self,
        workspace_root: Path,
        required_files: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        seen: set[Tuple[str, Tuple[str, ...]]] = set()
        candidate_roots = self._candidate_test_roots(workspace_root, required_files)

        for root in candidate_roots:
            for command in self._test_commands_for_root(workspace_root, root):
                key = (str(command["cwd"]), tuple(str(part) for part in command["command"]))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(command)

        if specs:
            return specs

        for root in self._scan_fallback_test_roots(workspace_root):
            for command in self._test_commands_for_root(workspace_root, root):
                key = (str(command["cwd"]), tuple(str(part) for part in command["command"]))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(command)
        return specs

    def _candidate_test_roots(self, workspace_root: Path, required_files: List[Dict[str, str]]) -> List[Path]:
        roots: List[Path] = []
        seen: set[Path] = set()

        def add(root: Optional[Path]) -> None:
            if root is None:
                return
            if root in seen:
                return
            seen.add(root)
            roots.append(root)

        for item in required_files:
            path = self._resolve_workspace_path(workspace_root, item.get("path"))
            if path is None:
                continue
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
                continue
            candidate = path if path.is_dir() else path.parent
            while True:
                if candidate == workspace_root or workspace_root in candidate.parents:
                    add(candidate)
                if candidate == workspace_root:
                    break
                if workspace_root not in candidate.parents:
                    break
                candidate = candidate.parent

        add(workspace_root)
        roots.sort(key=lambda path: (len(path.relative_to(workspace_root).parts), str(path)), reverse=True)
        return roots

    def _scan_fallback_test_roots(self, workspace_root: Path) -> List[Path]:
        roots: List[Path] = []
        seen: set[Path] = set()
        ignored_dirs = {
            ".git",
            ".idea",
            ".next",
            ".venv",
            "node_modules",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            "_runtime",
        }

        for path in workspace_root.rglob("*"):
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.is_dir() and path.name == "tests":
                candidate = path.parent
            elif path.is_file() and path.name in {"package.json", "pyproject.toml", "pytest.ini"}:
                candidate = path.parent
            else:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            roots.append(candidate)
        return roots

    def _test_commands_for_root(self, workspace_root: Path, root: Path) -> List[Dict[str, Any]]:
        commands: List[Dict[str, Any]] = []
        rel_cwd = "." if root == workspace_root else str(root.relative_to(workspace_root))

        def add(command: List[str]) -> None:
            commands.append(
                {
                    "cwd": rel_cwd,
                    "command": command,
                    "display": self._format_test_command_display(rel_cwd, command),
                }
            )

        if (root / "scripts" / "ci" / "test.sh").exists():
            add(["scripts/ci/test.sh"])
        if (root / "pytest.ini").exists() or (root / "tests").exists():
            add(["pytest", "-q"])
        package_json = root / "package.json"
        if package_json.exists():
            try:
                payload = json.loads(package_json.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            scripts = payload.get("scripts") if isinstance(payload, dict) else {}
            if isinstance(scripts, dict) and "test" in scripts:
                add(self._node_test_command(root, payload))
        return commands

    def _node_test_command(self, package_root: Path, package_payload: Dict[str, Any]) -> List[str]:
        package_manager = package_payload.get("packageManager")
        if isinstance(package_manager, str):
            normalized = package_manager.strip().lower()
            if normalized.startswith("pnpm@"):
                return ["pnpm", "test"]
            if normalized.startswith("yarn@"):
                return ["yarn", "test"]
        if (package_root / "pnpm-lock.yaml").exists():
            return ["pnpm", "test"]
        if (package_root / "yarn.lock").exists():
            return ["yarn", "test"]
        return ["npm", "test"]

    def _format_test_command_display(self, rel_cwd: str, command: List[str]) -> str:
        rendered = " ".join(shlex.quote(part) for part in command)
        if rel_cwd in {"", "."}:
            return rendered
        return f"cd {shlex.quote(rel_cwd)} && {rendered}"

    def _render_context_markdown(self, payload: Dict[str, Any]) -> str:
        lines = [
            f"# Context Pack: {payload['title']}",
            "",
            f"- Work item: `{payload['work_item_id']}`",
            f"- Goal: {payload['goal']}",
            f"- Generated: {payload['generated_at']}",
            "",
            "## Acceptance Criteria",
        ]
        for item in payload.get("acceptance_criteria") or ["No explicit acceptance criteria captured"]:
            lines.append(f"- {item}")
        lines.extend(["", "## Required Files"])
        for item in payload.get("required_files", []):
            lines.append(f"- `{item['path']}`: {item['reason']}")
        lines.extend(["", "## Test Commands"])
        for command in payload.get("test_commands", []) or ["No explicit test commands detected"]:
            lines.append(f"- `{command}`")
        lines.extend(["", "## Open Questions"])
        for item in payload.get("open_questions", []) or ["None"]:
            lines.append(f"- {item}")
        return "\n".join(lines) + "\n"

    def _render_review_markdown(self, report: Dict[str, Any]) -> str:
        lines = [
            f"# Review Report: {report['work_item_id']}",
            "",
            f"- Verdict: `{report['verdict']}`",
            f"- Summary: {report['summary']}",
            f"- Checked: {report['checked_at']}",
            "",
            "## Blocking Findings",
        ]
        for item in report.get("blocking_findings") or ["None"]:
            lines.append(f"- {item}")
        lines.extend(["", "## Warnings"])
        for item in report.get("warnings") or ["None"]:
            lines.append(f"- {item}")
        return "\n".join(lines) + "\n"

    def _serialize_qa_report(self, qa_result: QAResult) -> Dict[str, Any]:
        gates = []
        for result in qa_result.gate_results:
            gates.append(
                {
                    "id": result.gate_id,
                    "name": result.gate_name,
                    "status": self._map_qa_verdict(result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict)),
                    "findings": [
                        {
                            "severity": finding.severity,
                            "message": finding.message,
                            "file": finding.file_path,
                            "line": finding.line_number,
                            "rule_id": finding.rule_id,
                            "suggestion": finding.suggestion,
                        }
                        for finding in result.findings
                    ],
                }
            )
        summary = f"{qa_result.verdict.value.upper()}: {len(qa_result.all_findings)} findings ({len(qa_result.blocking_findings)} blocking)"
        return {
            "work_item_id": qa_result.step_run_id,
            "verdict": self._map_qa_verdict(qa_result.verdict.value),
            "summary": summary,
            "duration_seconds": qa_result.duration_seconds,
            "gates": gates,
            "generated_at": self._now_iso(),
        }

    def _render_qa_markdown(self, report: Dict[str, Any]) -> str:
        lines = [
            f"# Test Report: {report['work_item_id']}",
            "",
            f"- Verdict: `{report['verdict']}`",
            f"- Summary: {report['summary']}",
            f"- Generated: {report['generated_at']}",
            "",
            "## Gates",
        ]
        for gate in report.get("gates", []):
            lines.append(f"- `{gate['id']}`: {gate['status']}")
        return "\n".join(lines) + "\n"

    def _blocking_clarifications(self, project_id: int, protocol_run_id: int, step_run_id: int) -> int:
        clarifications = self.db.list_clarifications(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            status="open",
        )
        return sum(1 for item in clarifications if bool(getattr(item, "blocking", False)))

    def _evaluate_blocking_policy_findings(self, step_run_id: int, run, project) -> int:
        service = PolicyService(self.context, self.db)
        findings = service.evaluate_step(step_run_id, repo_root=self._workspace_root(run, project))
        blocking = [item for item in findings if str(item.severity).lower() in {"error", "block", "blocking"}]
        return len(blocking)

    def _context_open_questions(
        self,
        entry_points: List[Dict[str, str]],
        required_files: List[Dict[str, str]],
        test_commands: List[str],
    ) -> List[str]:
        questions: List[str] = []
        code_files = [
            item for item in required_files
            if str(item.get("path", "")).endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rb", ".java"))
        ]
        if not code_files:
            questions.append("No code files were confidently identified for this task. Add likely modules or entry points.")
        if len(entry_points) <= 1:
            questions.append("Context tracing found too few entry points. Confirm the primary files or call chain.")
        if not test_commands:
            questions.append("No test command was detected. Add the exact validation command before QA.")
        return questions

    def _ensure_context_clarifications(
        self,
        *,
        project_id: int,
        protocol_run_id: int,
        step_run_id: int,
        title: str,
        open_questions: List[str],
    ) -> List[Dict[str, Any]]:
        if not open_questions:
            return []

        refs: List[Dict[str, Any]] = []
        for idx, question in enumerate(open_questions, start=1):
            key = f"task-cycle-context-{step_run_id}-{idx}"
            row = self.db.upsert_clarification(
                scope=f"step:{step_run_id}",
                project_id=project_id,
                protocol_run_id=protocol_run_id,
                step_run_id=step_run_id,
                key=key,
                question=f"{title}: {question}",
                recommended={"value": "Add likely files, modules, or exact test commands."},
                options=None,
                applies_to="execution",
                blocking=False,
            )
            refs.append(
                {
                    "id": row.id,
                    "key": row.key,
                    "question": row.question,
                    "blocking": bool(row.blocking),
                }
            )
        return refs

    def _seed_task_cycle_metadata(
        self,
        protocol_run_id: int,
        *,
        owner_agent: Optional[str],
        helper_agents: List[str],
    ) -> None:
        run = self.db.get_protocol_run(protocol_run_id)
        project = self.db.get_project(run.project_id)
        resolved_owner_agent = self._resolve_owner_agent(project.id, owner_agent)
        protocol_metadata = dict(run.speckit_metadata or {})
        protocol_metadata["task_cycle"] = True
        self.db.update_protocol_windmill(run.id, speckit_metadata=protocol_metadata)
        for step in self.db.list_step_runs(protocol_run_id):
            if resolved_owner_agent and resolved_owner_agent != step.assigned_agent:
                self.db.update_step_assigned_agent(step.id, resolved_owner_agent)
                step = self.db.get_step_run(step.id)
            state = self._task_cycle_state(step, project)
            state["owner_agent"] = resolved_owner_agent or step.assigned_agent
            state["helper_agents"] = self._string_list(helper_agents)
            self._persist_task_cycle_state(step, state)

    def _default_exec_engine_id(self, project_id: int) -> str:
        candidate: Optional[str] = None
        try:
            cfg = AgentConfigService(self.context, db=self.db)
            candidate = cfg.get_default_engine_id(
                "exec",
                project_id=project_id,
                fallback=self.context.config.engine_defaults.get("exec"),
            )
        except Exception:
            candidate = self.context.config.engine_defaults.get("exec")
        if not isinstance(candidate, str) or not candidate.strip():
            return "opencode"
        return candidate.strip()

    def _resolve_owner_agent(self, project_id: int, owner_agent: Optional[str]) -> Optional[str]:
        candidate = self._string_or_none(owner_agent)
        if candidate is None:
            return None
        if candidate.lower() in {"dev", "developer", "default", "exec"}:
            return self._default_exec_engine_id(project_id)
        return candidate

    def _write_rework_pack(
        self,
        *,
        project,
        run,
        step: StepRun,
        source: str,
        findings: List[str],
        warnings: Optional[List[str]] = None,
    ) -> None:
        refs = self._artifact_refs(project, step)
        task_dir = Path(refs["task_dir"])
        task_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "work_item_id": step.id,
            "protocol_run_id": run.id,
            "project_id": project.id,
            "source": source,
            "reason": f"{source} requires rework",
            "findings": [item for item in findings if item],
            "required_actions": [item for item in findings if item],
            "warnings": [item for item in (warnings or []) if item],
            "supersedes_artifact_refs": {
                "review_report_json": refs["review_report_json"],
                "test_report_json": refs["test_report_json"],
            },
            "generated_at": self._now_iso(),
        }
        Path(refs["rework_pack_json"]).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _resolve_workspace_path(self, workspace_root: Path, raw: Optional[str]) -> Optional[Path]:
        if not raw:
            return None
        path = Path(raw)
        if path.is_absolute():
            return path
        return workspace_root / path

    def _relative_or_absolute(self, path: Path, workspace_root: Path, protocol_root: Path) -> str:
        for base in (workspace_root, protocol_root):
            try:
                return str(path.relative_to(base))
            except Exception:
                continue
        return str(path)

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _string_or_none(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise TaskCycleError(f"Failed to read JSON artifact {path}: {exc}") from exc

    def _map_qa_verdict(self, verdict: str) -> str:
        value = str(verdict).lower()
        if value in {"pass", "passed", "skip", "skipped"}:
            return "passed"
        if value == "warn":
            return "warning"
        return "failed"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _artifact_type_from_name(self, name: str) -> str:
        lower = name.lower()
        if lower.endswith(".log") or "log" in lower:
            return "log"
        if lower.endswith(".diff") or lower.endswith(".patch"):
            return "diff"
        if lower.endswith(".json"):
            return "json"
        if lower.endswith(".md") or lower.endswith(".txt"):
            return "text"
        return "file"

    def _iter_workspace_files(self, workspace_root: Path) -> Iterable[Path]:
        ignored_dirs = {
            ".git",
            ".idea",
            ".next",
            ".venv",
            "node_modules",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            "_runtime",
        }
        for path in workspace_root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in ignored_dirs for part in path.parts):
                continue
            yield path
