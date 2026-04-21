from __future__ import annotations

from time import monotonic as _monotonic
from typing import Any, List, Optional
from uuid import uuid4 as _uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from devgodzilla.api.routes._speckit_common import get_local_project_or_400
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.specification import SpecificationService
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.api.schemas import ClarificationOut
from pathlib import Path
import traceback as _traceback
from devgodzilla.logging import get_logger as _get_logger
_log = _get_logger(__name__)

router = APIRouter(tags=["SpecKit"])


def _check_policy_gate(db: Database, ctx: ServiceContext, project_id: int) -> Optional[List[dict]]:
    """Run policy evaluation for speckit operations. Returns findings if policy has blocking issues."""
    try:
        project = db.get_project(project_id)
        enforcement_mode = project.policy_enforcement_mode or "off"
        if enforcement_mode == "off":
            return None

        policy_service = PolicyService(ctx, db)
        findings = policy_service.evaluate_project(project_id)

        if enforcement_mode == "block":
            blocking = [f for f in findings if f.severity == "error"]
            if blocking:
                return [{"code": f.code, "severity": f.severity, "message": f.message,
                         "scope": f.scope, "suggested_fix": f.suggested_fix} for f in blocking]
        return None
    except Exception:
        return None  # Don't block speckit on policy errors


class SpecKitResponse(BaseModel):
    success: bool
    path: Optional[str] = None
    constitution_hash: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class ConstitutionRequest(BaseModel):
    content: str = Field(..., min_length=10)


class SpecifyRequest(BaseModel):
    description: str = Field(..., min_length=10)
    feature_name: Optional[str] = None
    base_branch: Optional[str] = None


class SpecifyResponse(BaseModel):
    success: bool
    spec_path: Optional[str] = None
    spec_number: Optional[int] = None
    feature_name: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: Optional[str] = None
    spec_root: Optional[str] = None
    error: Optional[str] = None


class PlanRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None
    context: Optional[str] = None


class PlanResponse(BaseModel):
    success: bool
    plan_path: Optional[str] = None
    data_model_path: Optional[str] = None
    contracts_path: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class TasksRequest(BaseModel):
    plan_path: str
    spec_run_id: Optional[int] = None


class TasksResponse(BaseModel):
    success: bool
    tasks_path: Optional[str] = None
    task_count: int = 0
    parallelizable_count: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ClarificationEntry(BaseModel):
    question: str
    answer: str


class ClarifyRequest(BaseModel):
    spec_path: str
    entries: List[ClarificationEntry] = Field(default_factory=list)
    notes: Optional[str] = None
    spec_run_id: Optional[int] = None


class ClarifyResponse(BaseModel):
    success: bool
    spec_path: Optional[str] = None
    clarifications_added: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ChecklistRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None


class ChecklistResponse(BaseModel):
    success: bool
    checklist_path: Optional[str] = None
    item_count: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class AnalyzeRequest(BaseModel):
    spec_path: str
    plan_path: Optional[str] = None
    tasks_path: Optional[str] = None
    spec_run_id: Optional[int] = None


class AnalyzeResponse(BaseModel):
    success: bool
    report_path: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ImplementRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None


class ImplementResponse(BaseModel):
    success: bool
    run_path: Optional[str] = None
    metadata_path: Optional[str] = None
    protocol_id: Optional[int] = None
    protocol_root: Optional[str] = None
    step_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


def _service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> SpecificationService:
    return SpecificationService(ctx, db)


@router.post("/projects/{project_id}/speckit/init", response_model=SpecKitResponse)
def init_project_speckit(
    project_id: int,
    request: Optional[ConstitutionRequest] = None,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = get_local_project_or_400(db, project_id)
    constitution_content = request.content if request else None
    if constitution_content is None:
        policy_service = PolicyService(ctx, db)
        effective = policy_service.resolve_effective_policy(
            project_id,
            repo_root=Path(project.local_path).expanduser(),
            include_repo_local=True,
        )
        constitution_content = policy_service.render_constitution(effective)
    result = service.init_project(
        project.local_path,
        constitution_content=constitution_content,
        project_id=project_id,
    )
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.get("/projects/{project_id}/speckit/constitution")
def get_project_constitution(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    content = service.get_constitution(project.local_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Constitution not found")
    return {"content": content}


@router.put("/projects/{project_id}/speckit/constitution", response_model=SpecKitResponse)
def put_project_constitution(
    project_id: int,
    request: ConstitutionRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = get_local_project_or_400(db, project_id)
    result = service.save_constitution(project.local_path, request.content, project_id=project_id)
    policy_service = PolicyService(ctx, db)
    override, meta = policy_service.policy_override_from_constitution(request.content)
    updates: dict[str, Any] = {}
    if isinstance(meta.get("key"), str):
        updates["policy_pack_key"] = meta["key"]
    if isinstance(meta.get("version"), str):
        updates["policy_pack_version"] = meta["version"]
    if override is not None:
        updates["policy_overrides"] = override
    if updates:
        db.update_project_policy(project_id, **updates)
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.post("/projects/{project_id}/speckit/constitution/sync", response_model=SpecKitResponse)
def sync_project_constitution(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = get_local_project_or_400(db, project_id)
    policy_service = PolicyService(ctx, db)
    effective = policy_service.resolve_effective_policy(
        project_id,
        repo_root=Path(project.local_path).expanduser(),
        include_repo_local=True,
    )
    constitution_content = policy_service.render_constitution(effective)
    result = service.save_constitution(project.local_path, constitution_content, project_id=project_id)
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.post("/projects/{project_id}/speckit/specify", response_model=SpecifyResponse)
def project_speckit_specify(
    project_id: int,
    request: SpecifyRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    import os as _os
    import threading as _threading

    _invocation_id = _uuid4().hex[:12]
    _caller_trace = "".join(_traceback.format_stack(limit=8)[-5:-1])
    _thread = _threading.current_thread()
    _pid = _os.getpid()
    _log.info(
        "project_speckit_specify_invoked",
        extra={
            "project_id": project_id,
            "invocation_id": _invocation_id,
            "pid": _pid,
            "thread_name": _thread.name,
            "thread_id": _thread.ident,
            "feature_name": request.feature_name,
            "base_branch": request.base_branch,
            "description_len": len(request.description),
            "description_preview": request.description[:120],
            "trace": _caller_trace,
        },
    )

    project = get_local_project_or_400(db, project_id)
    _log.info(
        "project_speckit_specify_project_resolved",
        extra={
            "project_id": project_id,
            "invocation_id": _invocation_id,
            "local_path": project.local_path,
        },
    )

    # Emit start event
    try:
        db.append_event(
            protocol_run_id=None,
            project_id=project_id,
            event_type="speckit_specify_started",
            message=f"Starting spec generation: {request.description[:50]}...",
            metadata={
                "feature_name": request.feature_name,
                "description_preview": request.description[:100],
            },
        )
    except Exception:
        pass  # Don't fail the request if event emission fails

    _started_at = _monotonic()
    _log.info(
        "project_speckit_specify_run_specify_started",
        extra={
            "project_id": project_id,
            "invocation_id": _invocation_id,
            "local_path": project.local_path,
        },
    )
    try:
        result = service.run_specify(
            project.local_path,
            request.description,
            feature_name=request.feature_name,
            base_branch=request.base_branch,
            project_id=project_id,
        )
    except Exception:
        _log.exception(
            "project_speckit_specify_run_specify_failed",
            extra={
                "project_id": project_id,
                "invocation_id": _invocation_id,
                "elapsed_ms": round((_monotonic() - _started_at) * 1000, 3),
                "local_path": project.local_path,
            },
        )
        raise

    _log.info(
        "project_speckit_specify_run_specify_finished",
        extra={
            "project_id": project_id,
            "invocation_id": _invocation_id,
            "elapsed_ms": round((_monotonic() - _started_at) * 1000, 3),
            "success": result.success,
            "spec_run_id": result.spec_run_id,
            "spec_number": result.spec_number,
            "result_feature_name": result.feature_name,
            "spec_path": result.spec_path,
            "worktree_path": result.worktree_path,
            "branch_name": result.branch_name,
            "base_branch": result.base_branch,
            "error": result.error,
        },
    )

    # Emit result event
    try:
        if result.success:
            db.append_event(
                protocol_run_id=None,
                project_id=project_id,
                event_type="speckit_specify_completed",
                message=f"Spec generated: {result.feature_name}",
                metadata={
                    "spec_number": result.spec_number,
                    "feature_name": result.feature_name,
                    "spec_path": result.spec_path,
                    "spec_run_id": result.spec_run_id,
                },
            )
        else:
            db.append_event(
                protocol_run_id=None,
                project_id=project_id,
                event_type="speckit_specify_failed",
                message=f"Spec generation failed: {result.error or 'Unknown error'}",
                metadata={
                    "feature_name": request.feature_name,
                    "error": result.error,
                    "spec_run_id": result.spec_run_id,
                },
            )
    except Exception:
        pass  # Don't fail the request if event emission fails
    
    return SpecifyResponse(
        success=result.success,
        spec_path=result.spec_path,
        spec_number=result.spec_number,
        feature_name=result.feature_name,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        branch_name=result.branch_name,
        base_branch=result.base_branch,
        spec_root=result.spec_root,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/plan", response_model=PlanResponse)
def project_speckit_plan(
    project_id: int,
    request: PlanRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    result = service.run_plan(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
        context=request.context,
    )
    return PlanResponse(
        success=result.success,
        plan_path=result.plan_path,
        data_model_path=result.data_model_path,
        contracts_path=result.contracts_path,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/tasks", response_model=TasksResponse)
def project_speckit_tasks(
    project_id: int,
    request: TasksRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    result = service.run_tasks(
        project.local_path,
        request.plan_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return TasksResponse(
        success=result.success,
        tasks_path=result.tasks_path,
        task_count=result.task_count,
        parallelizable_count=result.parallelizable_count,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/clarify", response_model=ClarifyResponse)
def project_speckit_clarify(
    project_id: int,
    request: ClarifyRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    result = service.run_clarify(
        project.local_path,
        request.spec_path,
        entries=[entry.model_dump() for entry in request.entries],
        notes=request.notes,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ClarifyResponse(
        success=result.success,
        spec_path=result.spec_path,
        clarifications_added=result.clarifications_added,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/checklist", response_model=ChecklistResponse)
def project_speckit_checklist(
    project_id: int,
    request: ChecklistRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    # Policy gate
    policy_violations = _check_policy_gate(db, ctx, project_id)
    if policy_violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Policy violations blocked this operation",
                "findings": policy_violations,
            }
        )
    result = service.run_checklist(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ChecklistResponse(
        success=result.success,
        checklist_path=result.checklist_path,
        item_count=result.item_count,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/analyze", response_model=AnalyzeResponse)
def project_speckit_analyze(
    project_id: int,
    request: AnalyzeRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    # Policy gate
    policy_violations = _check_policy_gate(db, ctx, project_id)
    if policy_violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Policy violations blocked this operation",
                "findings": policy_violations,
            }
        )
    result = service.run_analyze(
        project.local_path,
        request.spec_path,
        plan_path=request.plan_path,
        tasks_path=request.tasks_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return AnalyzeResponse(
        success=result.success,
        report_path=result.report_path,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# Detect ambiguities (AI-powered clarification)
# ---------------------------------------------------------------------------

class DetectAmbiguitiesRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None
    context: Optional[str] = None


class DetectAmbiguitiesResponse(BaseModel):
    success: bool
    clarifications: List[ClarificationOut] = Field(default_factory=list)
    error: Optional[str] = None


def _clarification_to_out(c: Any) -> ClarificationOut:
    return ClarificationOut(
        id=c.id,
        scope=getattr(c, "scope", None),
        project_id=getattr(c, "project_id", None),
        protocol_run_id=getattr(c, "protocol_run_id", None),
        step_run_id=getattr(c, "step_run_id", None),
        key=getattr(c, "key", None),
        question=c.question,
        status=getattr(c, "status", "open"),
        options=getattr(c, "options", None),
        recommended=getattr(c, "recommended", None),
        applies_to=getattr(c, "applies_to", None),
        blocking=getattr(c, "blocking", None),
        answer=getattr(c, "answer", None),
        created_at=str(c.created_at) if hasattr(c, "created_at") and c.created_at else None,
        answered_at=str(c.answered_at) if hasattr(c, "answered_at") and c.answered_at else None,
        answered_by=getattr(c, "answered_by", None),
    )


@router.post(
    "/projects/{project_id}/speckit/detect-ambiguities",
    response_model=DetectAmbiguitiesResponse,
)
def project_speckit_detect_ambiguities(
    project_id: int,
    request: DetectAmbiguitiesRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Use AI to detect ambiguities in a specification and return clarification questions."""
    project = get_local_project_or_400(db, project_id)

    # Resolve spec file
    spec_file = Path(project.local_path) / request.spec_path
    if not spec_file.exists():
        raise HTTPException(404, f"Spec file not found: {request.spec_path}")

    try:
        content = spec_file.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(500, f"Failed to read spec file: {exc}")

    # Build context: spec content + optional extra context
    context_parts: List[str] = []
    if request.context:
        context_parts.append(request.context)

    # Try to load constitution for additional context
    try:
        constitution_path = Path(project.local_path) / ".speckit" / "constitution.md"
        if constitution_path.exists():
            context_parts.append(
                "Project constitution:\n" + constitution_path.read_text(encoding="utf-8")[:4000]
            )
    except Exception:
        pass

    clarifier = ClarifierService(ctx, db)
    detected = clarifier.detect_ambiguities(
        content,
        context="\n\n".join(context_parts),
        project_id=project_id,
        persist=True,
    )

    return DetectAmbiguitiesResponse(
        success=True,
        clarifications=[_clarification_to_out(c) for c in detected],
    )


@router.post("/projects/{project_id}/speckit/implement", response_model=ImplementResponse)
def project_speckit_implement(
    project_id: int,
    request: ImplementRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
    service: SpecificationService = Depends(_service),
):
    project = get_local_project_or_400(db, project_id)
    # Policy gate
    policy_violations = _check_policy_gate(db, ctx, project_id)
    if policy_violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Policy violations blocked this operation",
                "findings": policy_violations,
            }
        )
    result = service.run_implement(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ImplementResponse(
        success=result.success,
        run_path=result.run_path,
        metadata_path=result.metadata_path,
        protocol_id=result.protocol_id,
        protocol_root=result.protocol_root,
        step_count=result.step_count,
        warnings=result.warnings,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )
