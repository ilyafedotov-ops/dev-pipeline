from __future__ import annotations

import concurrent.futures
import threading
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from devgodzilla.api import schemas

# Timeout for synchronous attempt before falling back to background (seconds)
_SYNC_TIMEOUT = 2.0
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.task_cycle import TaskCycleError, TaskCycleService

logger = get_logger(__name__)

router = APIRouter()


class WorkItemQARequest(BaseModel):
    gates: Optional[List[str]] = None


def _task_cycle_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> TaskCycleService:
    return TaskCycleService(ctx, db)


@router.get("/projects/{project_id}/task-cycle", response_model=List[schemas.WorkItemOut])
def list_task_cycle_work_items(
    project_id: int,
    protocol_run_id: Optional[int] = Query(default=None),
    db: Database = Depends(get_db),
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return service.list_work_items(project_id, protocol_run_id=protocol_run_id)
    except TaskCycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/projects/{project_id}/brownfield/run",
    response_model=schemas.BrownfieldRunOut,
    responses={202: {"model": schemas.BrownfieldRunOut}},
)
def start_brownfield_run(
    project_id: int,
    request: schemas.BrownfieldRunRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
    service: TaskCycleService = Depends(_task_cycle_service),
):
    """Start a brownfield run.

    Attempts to run synchronously first (fast when engines are mocked).
    Falls back to background execution for real AI engine calls that take minutes,
    returning 202 Accepted with a background task.
    """
    # Validate project exists synchronously
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")

    # Try synchronous execution first (works when engines are mocked/stubbed)
    import threading
    _sync_result = [None]
    _sync_exc = [None]
    _sync_done = threading.Event()

    def _do_sync():
        try:
            _sync_result[0] = service.start_brownfield_run(project_id, request)
        except Exception as e:
            _sync_exc[0] = e
        finally:
            _sync_done.set()

    t = threading.Thread(target=_do_sync, daemon=True)
    t.start()
    completed = _sync_done.wait(timeout=_SYNC_TIMEOUT)

    if completed:
        if _sync_exc[0]:
            # Re-raise validation errors directly (HTTPExceptions + domain errors)
            from fastapi import HTTPException
            from devgodzilla.services.task_cycle import TaskCycleError
            if isinstance(_sync_exc[0], (HTTPException, TaskCycleError)):
                if isinstance(_sync_exc[0], TaskCycleError):
                    raise HTTPException(status_code=400, detail=str(_sync_exc[0]))
                raise _sync_exc[0]
            # For other errors, log and fall through to background
            logger.warning(
                "brownfield_sync_error_switching_to_background",
                extra={"project_id": project_id, "error": str(_sync_exc[0])},
            )
        else:
            return _sync_result[0]

    # Thread is still alive (slow AI call) — fall through to background
    logger.info(
            "brownfield_sync_timeout_switching_to_background",
            extra={"project_id": project_id},
        )

    if background_tasks is None:
        raise RuntimeError("Background tasks not available")

    def _run_brownfield():
        try:
            # Wait for sync thread to finish before starting background work
            _sync_done.wait(timeout=120)
            # Guard: if sync thread already completed successfully, skip
            if _sync_result[0] is not None and _sync_result[0].success:
                logger.info(
                    "brownfield_bg_skipped_sync_succeeded",
                    extra={"project_id": project_id},
                )
                return
            service.start_brownfield_run(project_id, request)
        except Exception as bg_exc:
            logger.exception(
                "brownfield_background_run_failed",
                extra={"project_id": project_id, "error": str(bg_exc)},
            )

    background_tasks.add_task(_run_brownfield)

    return JSONResponse(
        status_code=202,
        content=schemas.BrownfieldRunOut(
            success=True,
            project_id=project_id,
            output_mode=request.output_mode,
            warnings=["Brownfield run started in background. Poll /task-cycle for results."],
        ).model_dump(),
    )


@router.get("/work-items/{work_item_id}", response_model=schemas.WorkItemOut)
def get_work_item(
    work_item_id: int,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.get_work_item(work_item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")


@router.get("/work-items/{work_item_id}/artifacts/{artifact_key}/content", response_model=schemas.ArtifactContentOut)
def get_work_item_artifact_content(
    work_item_id: int,
    artifact_key: str,
    max_bytes: int = Query(default=200_000, ge=1, le=2_000_000),
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.read_artifact_content(work_item_id, artifact_key, max_bytes=max_bytes)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail)


@router.post("/work-items/{work_item_id}/build-context", response_model=schemas.WorkItemOut)
def build_context(
    work_item_id: int,
    request: schemas.BuildContextRequest,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.build_context(work_item_id, refresh=request.refresh)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/work-items/{work_item_id}/actions/implement", response_model=schemas.WorkItemOut)
def implement_work_item(
    work_item_id: int,
    request: schemas.WorkItemImplementRequest,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.implement(work_item_id, owner_agent=request.owner_agent)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error implementing work item %s", work_item_id)
        raise HTTPException(status_code=500, detail="Internal server error: " + str(exc))


@router.post("/work-items/{work_item_id}/actions/review", response_model=schemas.WorkItemReviewOut)
def review_work_item(
    work_item_id: int,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        _, review = service.review(work_item_id)
        return review
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/work-items/{work_item_id}/actions/qa", response_model=schemas.WorkItemQAOut)
def qa_work_item(
    work_item_id: int,
    request: WorkItemQARequest,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.qa(work_item_id, gates=request.gates)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/work-items/{work_item_id}/actions/mark-pr-ready", response_model=schemas.WorkItemOut)
def mark_pr_ready(
    work_item_id: int,
    service: TaskCycleService = Depends(_task_cycle_service),
):
    try:
        return service.mark_pr_ready(work_item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Work item not found")
    except TaskCycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
