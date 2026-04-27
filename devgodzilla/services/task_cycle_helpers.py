from __future__ import annotations

import concurrent.futures
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.engines import EngineRequest, SandboxMode, get_registry
from devgodzilla.logging import get_logger
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.base import ServiceContext

logger = get_logger(__name__)


class TaskCycleHelperRunner:
    """Runs bounded helper subtasks inside a work item without creating workflow lanes."""

    def __init__(self, context: ServiceContext, db) -> None:
        self.context = context
        self.db = db
        self.config = context.config

    def build_summary(self, helper_agents: List[str], helper_runs: Any = None) -> Optional[str]:
        if not helper_agents:
            return None
        run_map = self.normalize_runs(helper_runs)
        if run_map:
            completed = sum(1 for item in run_map.values() if item.get("status") == "completed")
            failed = sum(1 for item in run_map.values() if item.get("status") == "failed")
            running = sum(1 for item in run_map.values() if item.get("status") == "running")
            pending = sum(1 for item in run_map.values() if item.get("status") == "pending")
            parts = []
            if completed:
                parts.append(f"{completed} completed")
            if failed:
                parts.append(f"{failed} failed")
            if running:
                parts.append(f"{running} running")
            if pending:
                parts.append(f"{pending} pending")
            if parts:
                return f"{len(helper_agents)} helpers under the owner: {', '.join(parts)}"

        count = len(helper_agents)
        noun = "helper" if count == 1 else "helpers"
        joined = ", ".join(helper_agents[:4])
        suffix = " (internal delegation only)" if count <= 4 else f", +{count - 4} more (internal delegation only)"
        return f"{count} {noun} configured under the owner: {joined}{suffix}"

    def normalize_runs(self, value: Any) -> Dict[str, Dict[str, Any]]:
        if not isinstance(value, dict):
            return {}
        payload: Dict[str, Dict[str, Any]] = {}
        for key, item in value.items():
            if not isinstance(item, dict):
                continue
            payload[str(key)] = dict(item)
        return payload

    def run_subtasks(
        self,
        *,
        project_id: int,
        protocol_run_id: int,
        step_run_id: int,
        step_name: str,
        owner_agent: Optional[str],
        helper_agents: List[str],
        context_pack: Dict[str, Any],
        task_dir: Path,
        working_dir: Path,
        default_engine_id: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        if not helper_agents:
            return {}

        helpers_dir = self._helper_artifacts_dir(task_dir)
        helpers_dir.mkdir(parents=True, exist_ok=True)
        max_workers = max(
            1,
            min(
                int(self.config.task_cycle_helper_parallelism or 1),
                len(helper_agents),
            ),
        )
        runs: Dict[str, Dict[str, Any]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    self.execute_helper_subtask,
                    project_id=project_id,
                    protocol_run_id=protocol_run_id,
                    step_run_id=step_run_id,
                    step_name=step_name,
                    owner_agent=owner_agent,
                    helper_agent=helper_agent,
                    context_pack=context_pack,
                    helper_dir=self._helper_task_dir(task_dir, helper_agent),
                    working_dir=working_dir,
                    default_engine_id=default_engine_id,
                ): helper_agent
                for helper_agent in helper_agents
            }
            for future in concurrent.futures.as_completed(futures):
                helper_agent = futures[future]
                try:
                    runs[helper_agent] = future.result()
                except Exception as exc:
                    helper_dir = self._helper_task_dir(task_dir, helper_agent)
                    helper_dir.mkdir(parents=True, exist_ok=True)
                    failure = {
                        "helper_agent": helper_agent,
                        "status": "failed",
                        "engine_id": owner_agent or default_engine_id,
                        "role": helper_agent,
                        "artifact_dir": str(helper_dir),
                        "summary": f"Helper subtask failed: {exc}",
                        "started_at": self._now_iso(),
                        "completed_at": self._now_iso(),
                    }
                    (helper_dir / "result.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
                    runs[helper_agent] = failure

        ordered_runs = {helper: runs[helper] for helper in helper_agents if helper in runs}
        (helpers_dir / "helper_summary.json").write_text(
            json.dumps(
                {
                    "work_item_id": step_run_id,
                    "protocol_run_id": protocol_run_id,
                    "owner_agent": owner_agent,
                    "helpers": list(ordered_runs.values()),
                    "generated_at": self._now_iso(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return ordered_runs

    def execute_helper_subtask(
        self,
        *,
        project_id: int,
        protocol_run_id: int,
        step_run_id: int,
        step_name: str,
        owner_agent: Optional[str],
        helper_agent: str,
        context_pack: Dict[str, Any],
        helper_dir: Path,
        working_dir: Path,
        default_engine_id: Optional[str],
    ) -> Dict[str, Any]:
        helper_dir.mkdir(parents=True, exist_ok=True)
        started_at = self._now_iso()
        engine_id = self._resolve_helper_engine(project_id, helper_agent, owner_agent, default_engine_id)
        prompt_text = self._build_helper_prompt(
            helper_role=helper_agent,
            owner_agent=owner_agent,
            step_name=step_name,
            context_pack=context_pack,
        )
        request_payload = {
            "helper_agent": helper_agent,
            "engine_id": engine_id,
            "owner_agent": owner_agent,
            "prompt_text": prompt_text,
            "sandbox": "read-only",
        }
        (helper_dir / "request.json").write_text(json.dumps(request_payload, indent=2), encoding="utf-8")

        result = self.execute_helper_prompt(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            engine_id=engine_id,
            prompt_text=prompt_text,
            working_dir=working_dir,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        (helper_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (helper_dir / "stderr.log").write_text(stderr, encoding="utf-8")

        status = "completed" if result.success else "failed"
        payload = {
            "helper_agent": helper_agent,
            "status": status,
            "engine_id": engine_id,
            "role": helper_agent,
            "artifact_dir": str(helper_dir),
            "summary": self._summarize_helper_output(stdout, stderr, helper_agent, status),
            "started_at": started_at,
            "completed_at": self._now_iso(),
        }
        if result.error:
            payload["error"] = result.error
        (helper_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def execute_helper_prompt(
        self,
        *,
        project_id: int,
        protocol_run_id: int,
        step_run_id: int,
        engine_id: str,
        prompt_text: str,
        working_dir: Path,
    ):
        registry = get_registry()
        engine = registry.get(engine_id)
        if not engine.check_availability():
            raise RuntimeError(f"Helper engine unavailable: {engine_id}")

        request = EngineRequest(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            model=self._helper_model(engine_id, project_id=project_id),
            prompt_text=prompt_text,
            working_dir=str(working_dir),
            sandbox=SandboxMode.READ_ONLY,
            timeout=int(self.config.task_cycle_helper_timeout_seconds or 180),
            extra={},
        )
        reasoning = self._helper_reasoning_effort(engine_id, project_id=project_id)
        if reasoning:
            request.extra["reasoning_effort"] = reasoning
        return engine.execute(request)

    def _resolve_helper_engine(
        self,
        project_id: int,
        helper_agent: str,
        owner_agent: Optional[str],
        default_engine_id: Optional[str],
    ) -> str:
        cfg = AgentConfigService(self.context, db=self.db)
        candidate = str(helper_agent).strip() or None
        if candidate and cfg.get_agent(candidate, project_id=project_id):
            return candidate
        return owner_agent or default_engine_id or "opencode"

    def _helper_model(self, engine_id: str, *, project_id: int) -> Optional[str]:
        try:
            cfg = AgentConfigService(self.context, db=self.db)
            agent = cfg.get_agent(engine_id, project_id=project_id)
            if agent and isinstance(agent.default_model, str) and agent.default_model.strip():
                return agent.default_model.strip()
        except Exception:
            return None
        return None

    def _helper_reasoning_effort(self, engine_id: str, *, project_id: int) -> Optional[str]:
        try:
            cfg = AgentConfigService(self.context, db=self.db)
            agent = cfg.get_agent(engine_id, project_id=project_id)
            if agent and isinstance(agent.reasoning_effort, str) and agent.reasoning_effort.strip():
                return agent.reasoning_effort.strip()
        except Exception:
            return None
        return None

    def _helper_artifacts_dir(self, task_dir: Path) -> Path:
        return task_dir / "helpers"

    def _helper_task_dir(self, task_dir: Path, helper_agent: str) -> Path:
        slug = re.sub(r"[^a-z0-9._-]+", "-", helper_agent.strip().lower()).strip("-") or "helper"
        return self._helper_artifacts_dir(task_dir) / slug

    def _build_helper_prompt(
        self,
        *,
        helper_role: str,
        owner_agent: Optional[str],
        step_name: str,
        context_pack: Dict[str, Any],
    ) -> str:
        role_key = helper_role.strip().lower()
        role_instructions = {
            "trace": "Trace likely entry points, impacted modules, and call-flow risks. Do not modify files.",
            "tests": "Identify the most relevant test files and exact test commands for this change. Do not modify files.",
            "review": "Identify likely review concerns, style-guide risks, and policy-sensitive files. Do not modify files.",
            "docs": "Identify documentation files that must change and the expected documentation delta. Do not modify files.",
        }.get(
            role_key,
            "Provide focused supporting analysis for the owner agent. Do not modify files.",
        )
        compact_context = {
            "goal": context_pack.get("goal"),
            "acceptance_criteria": context_pack.get("acceptance_criteria"),
            "entry_points": context_pack.get("entry_points"),
            "required_files": context_pack.get("required_files"),
            "test_commands": context_pack.get("test_commands"),
            "review_focus": context_pack.get("review_focus"),
            "risks": context_pack.get("risks"),
        }
        return (
            f"# Helper Subtask: {helper_role}\n\n"
            f"You are a bounded helper under the owner agent `{owner_agent or 'unassigned'}` for work item `{step_name}`.\n"
            "Your task is advisory only. Stay read-only. Do not edit files, commit code, or create workflow lanes.\n\n"
            f"{role_instructions}\n\n"
            "Return concise findings with concrete file paths and actions the owner should take.\n\n"
            "## ContextPack\n\n```json\n"
            + json.dumps(compact_context, indent=2)
            + "\n```"
        )

    def _summarize_helper_output(
        self,
        stdout: str,
        stderr: str,
        helper_agent: str,
        status: str,
    ) -> str:
        if status != "completed":
            message = (stderr or stdout or f"{helper_agent} failed").strip()
            return message.splitlines()[0][:240] if message else f"{helper_agent} failed"
        text = (stdout or stderr).strip()
        if not text:
            return f"{helper_agent} completed with no output"
        return text.splitlines()[0][:240]

    def _now_iso(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
