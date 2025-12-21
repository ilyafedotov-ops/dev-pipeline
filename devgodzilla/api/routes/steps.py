from typing import List, Optional
from pathlib import Path
import subprocess

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from devgodzilla.api.dependencies import get_service_context
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.execution import ExecutionService
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.quality import QualityService
from devgodzilla.qa.gates import LintGate, TypeGate, TestGate

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database

router = APIRouter()


class StepQARequest(BaseModel):
    gates: Optional[List[str]] = None


class StepAssignAgentRequest(BaseModel):
    agent_id: str


def _workspace_root(run, project) -> Path:
    if run.worktree_path:
        return Path(run.worktree_path).expanduser()
    if project.local_path:
        return Path(project.local_path).expanduser()
    return Path.cwd()


def _protocol_root(run, workspace_root: Path) -> Path:
    if run.protocol_root:
        return Path(run.protocol_root).expanduser()
    specs = workspace_root / "specs" / run.protocol_name
    protocols = workspace_root / ".protocols" / run.protocol_name
    if specs.exists():
        return specs
    if protocols.exists():
        return protocols
    return specs


def _step_artifacts_dir(db: Database, step_id: int) -> Path:
    step = db.get_step_run(step_id)
    run = db.get_protocol_run(step.protocol_run_id)
    project = db.get_project(run.project_id)
    root = _protocol_root(run, _workspace_root(run, project))
    artifacts_dir = root / ".devgodzilla" / "steps" / str(step_id) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def _artifact_type_from_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".log") or "log" in lower:
        return "log"
    if lower.endswith(".diff") or lower.endswith(".patch"):
        return "diff"
    if lower.endswith(".md") and ("report" in lower or "qa" in lower):
        return "report"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".txt") or lower.endswith(".md"):
        return "text"
    return "file"


def _safe_child(base: Path, name: str) -> Path:
    if "/" in name or "\\" in name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid artifact id")
    candidate = (base / name).resolve()
    base_resolved = base.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise HTTPException(status_code=400, detail="Invalid artifact id")
    return candidate


def _policy_location(metadata: Optional[dict]) -> Optional[str]:
    if not metadata:
        return None
    if isinstance(metadata.get("location"), str):
        return metadata["location"]
    file_name = metadata.get("file") or metadata.get("path")
    section = metadata.get("section") or metadata.get("heading")
    if file_name and section:
        return f"{file_name}#{section}"
    if file_name:
        return str(file_name)
    if section:
        return str(section)
    return None


@router.get("/steps", response_model=List[schemas.StepOut])
def list_steps(
    protocol_run_id: int,
    db: Database = Depends(get_db)
):
    """List steps for a protocol run."""
    return db.list_step_runs(protocol_run_id)

@router.get("/steps/{step_id}", response_model=schemas.StepOut)
def get_step(
    step_id: int,
    db: Database = Depends(get_db)
):
    """Get a step by ID."""
    try:
        return db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")


@router.get("/steps/{step_id}/policy/findings", response_model=List[schemas.PolicyFindingOut])
def get_step_policy_findings(
    step_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Get policy violation findings for a step."""
    try:
        step = db.get_step_run(step_id)
        run = db.get_protocol_run(step.protocol_run_id)
        project = db.get_project(run.project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    repo_root = _workspace_root(run, project)
    policy_service = PolicyService(ctx, db)
    findings = policy_service.evaluate_step(step_id, repo_root=repo_root)

    return [
        schemas.PolicyFindingOut(
            code=f.code,
            severity=f.severity,
            message=f.message,
            scope=f.scope,
            location=_policy_location(f.metadata),
            suggested_fix=f.suggested_fix,
            metadata=f.metadata,
        )
        for f in findings
    ]


@router.post("/steps/{step_id}/actions/assign_agent", response_model=schemas.StepOut)
def assign_agent(
    step_id: int,
    request: StepAssignAgentRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Assign an agent to a step."""
    try:
        step = db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    try:
        run = db.get_protocol_run(step.protocol_run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    cfg = AgentConfigService(ctx, db=db)
    agent = cfg.get_agent(request.agent_id, project_id=run.project_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return db.update_step_assigned_agent(step_id, request.agent_id)


@router.get("/steps/{step_id}/quality", response_model=schemas.QualitySummaryOut)
def get_step_quality(
    step_id: int,
    db: Database = Depends(get_db),
):
    """Return a lightweight quality summary for a single step."""
    try:
        step = db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    qa_record = db.get_latest_qa_result(step_run_id=step_id)
    if not qa_record:
        checklist_items = [
            schemas.ChecklistItemOut(id="qa_ran", description="QA executed", passed=False, required=False),
        ]
        return schemas.QualitySummaryOut(
            protocol_run_id=step.protocol_run_id,
            score=0.0,
            gates=[],
            checklist=schemas.ChecklistResultOut(
                passed=0,
                total=len(checklist_items),
                items=checklist_items,
            ),
            overall_status="skipped",
            blocking_issues=0,
            warnings=0,
        )

    verdict = qa_record.verdict

    def to_status(v: str | None) -> str:
        if v in ("pass", "skip"):
            return "passed"
        if v == "warn":
            return "warning"
        if v in ("fail", "error"):
            return "failed"
        return "skipped"

    gates = []
    for g in qa_record.gate_results or []:
        findings = [
            schemas.QAFindingOut(
                severity=f.get("severity", ""),
                message=f.get("message", ""),
                file=f.get("file_path"),
                line=f.get("line_number"),
                rule_id=f.get("rule_id"),
                suggestion=f.get("suggestion"),
            )
            for f in (g.get("findings") or [])
        ]
        gates.append(
            schemas.GateResultOut(
                article=g.get("gate_id", ""),
                name=str(g.get("gate_name", g.get("gate_id", ""))).upper(),
                status=to_status(g.get("verdict")),
                findings=findings,
            )
        )

    blocking = 1 if verdict in ("fail", "error") else 0
    warnings = 1 if verdict == "warn" else 0
    score = 1.0 if verdict in ("pass", "skip") else 0.7 if verdict == "warn" else 0.0 if verdict in ("fail", "error") else 0.0
    overall_status = "failed" if blocking else "warning" if warnings else "passed"

    checklist_items = [
        schemas.ChecklistItemOut(id="qa_ran", description="QA executed", passed=verdict is not None, required=False),
    ]
    return schemas.QualitySummaryOut(
        protocol_run_id=step.protocol_run_id,
        score=score,
        gates=gates,
        checklist=schemas.ChecklistResultOut(passed=sum(1 for i in checklist_items if i.passed), total=len(checklist_items), items=checklist_items),
        overall_status=overall_status,
        blocking_issues=blocking,
        warnings=warnings,
    )


@router.post("/steps/{step_id}/actions/execute", response_model=schemas.StepOut)
def execute_step(
    step_id: int,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Execute a step (synchronous)."""
    try:
        step = db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    service = ExecutionService(ctx, db)
    result = service.execute_step(step_id)

    # Persist basic artifacts (logs + metadata + best-effort git diff) for UI
    try:
        import json

        artifacts_dir = _step_artifacts_dir(db, step_id)
        (artifacts_dir / "execution.log").write_text(result.stdout or "", encoding="utf-8")
        (artifacts_dir / "execution.stderr.log").write_text(result.stderr or "", encoding="utf-8")
        (artifacts_dir / "execution.meta.json").write_text(
            json.dumps(
                {
                    "engine_id": result.engine_id,
                    "model": result.model,
                    "success": result.success,
                    "tokens_used": result.tokens_used,
                    "cost_cents": result.cost_cents,
                    "duration_seconds": result.duration_seconds,
                    "error": result.error,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        run = db.get_protocol_run(step.protocol_run_id)
        project = db.get_project(run.project_id)
        cwd = _workspace_root(run, project)
        try:
            proc = subprocess.run(
                ["git", "diff"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                (artifacts_dir / "changes.diff").write_text(proc.stdout, encoding="utf-8")
        except Exception:
            pass
    except Exception:
        # Artifacts should never break execution endpoint
        pass
    return db.get_step_run(step_id)


@router.post("/steps/{step_id}/actions/qa", response_model=schemas.QAResultOut)
def qa_step(
    step_id: int,
    request: StepQARequest,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Run QA on a step."""
    try:
        step = db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    quality = QualityService(ctx, db)

    # If the user specified gates, only run those.
    gate_map = {
        "lint": LintGate(),
        "type": TypeGate(),
        "test": TestGate(),
    }
    gates_to_run = None
    if request.gates is not None:
        if len(request.gates) == 0:
            gates_to_run = []
        else:
            unknown = [g for g in request.gates if g not in gate_map]
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown gates: {', '.join(unknown)}")
            gates_to_run = [gate_map[g] for g in request.gates]

    qa = quality.run_qa(step_id, gates=gates_to_run)

    # Best-effort: if all steps are terminal, update protocol status to completed/failed.
    try:
        from devgodzilla.services.orchestrator import OrchestratorService

        orchestrator = OrchestratorService(context=ctx, db=db)
        orchestrator.check_and_complete_protocol(step.protocol_run_id)
    except Exception:
        pass

    # Generate human-readable report as an artifact (best-effort)
    report_path = None
    try:
        artifacts_dir = _step_artifacts_dir(db, step_id)
        report_path = quality.generate_quality_report(
            qa,
            artifacts_dir,
            step_name=db.get_step_run(step_id).step_name,
        )
    except Exception:
        report_path = None

    # Persist QA verdict + report metadata
    quality.persist_verdict(qa, step_id, report_path=report_path)

    def map_gate_status(v: str) -> str:
        if v == "pass":
            return "passed"
        if v == "warn":
            return "warning"
        if v == "skip":
            return "skipped"
        return "failed"

    verdict = "passed" if qa.verdict.value in ["pass", "skip"] else "warning" if qa.verdict.value == "warn" else "failed"
    summary = f"{qa.verdict.value.upper()}: {len(qa.all_findings)} findings ({len(qa.blocking_findings)} blocking)"

    gates = [
        schemas.QAGateOut(
            id=r.gate_id,
            name=r.gate_name,
            status=map_gate_status(r.verdict.value),
            findings=[
                schemas.QAFindingOut(
                    severity=f.severity,
                    message=f.message,
                    file=f.file_path,
                    line=f.line_number,
                    rule_id=f.rule_id,
                    suggestion=f.suggestion,
                )
                for f in r.findings
            ],
        )
        for r in qa.gate_results
    ]

    return schemas.QAResultOut(verdict=verdict, summary=summary, gates=gates)


@router.get("/steps/{step_id}/artifacts", response_model=List[schemas.ArtifactOut])
def list_step_artifacts(
    step_id: int,
    db: Database = Depends(get_db),
):
    """List artifacts for a step."""
    try:
        db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    artifacts_dir = _step_artifacts_dir(db, step_id)
    if not artifacts_dir.exists():
        return []

    items: List[schemas.ArtifactOut] = []
    for p in sorted(artifacts_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        items.append(
            schemas.ArtifactOut(
                id=p.name,
                type=_artifact_type_from_name(p.name),
                name=p.name,
                size=stat.st_size,
                created_at=None,
            )
        )
    return items


@router.get("/steps/{step_id}/artifacts/{artifact_id}/content", response_model=schemas.ArtifactContentOut)
def get_step_artifact_content(
    step_id: int,
    artifact_id: str,
    max_bytes: int = 200_000,
    db: Database = Depends(get_db),
):
    """Fetch artifact content for preview (truncates large files)."""
    try:
        db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    artifacts_dir = _step_artifacts_dir(db, step_id)
    path = _safe_child(artifacts_dir, artifact_id)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

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
        id=artifact_id,
        name=artifact_id,
        type=_artifact_type_from_name(artifact_id),
        content=content,
        truncated=truncated,
    )


@router.get("/steps/{step_id}/artifacts/{artifact_id}/download")
def download_step_artifact(
    step_id: int,
    artifact_id: str,
    db: Database = Depends(get_db),
):
    """Download artifact as a file."""
    try:
        db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    artifacts_dir = _step_artifacts_dir(db, step_id)
    path = _safe_child(artifacts_dir, artifact_id)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path=str(path), filename=path.name)
