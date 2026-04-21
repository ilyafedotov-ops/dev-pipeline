from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from devgodzilla.api.dependencies import get_windmill_client
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.windmill.client import WindmillClient

router = APIRouter(tags=["Windmill"])
logger = get_logger(__name__)


@router.get("/flows")
def list_flows(
    prefix: Optional[str] = Query(None, description="Optional flow path prefix"),
    windmill: WindmillClient = Depends(get_windmill_client),
) -> List[Dict[str, Any]]:
    flows = windmill.list_flows(prefix=prefix)
    items = [{"path": f.path, "name": f.name, "summary": f.summary} for f in flows]
    logger.info("windmill_flows_listed", extra=log_extra(prefix=prefix, result_count=len(items)))
    return items


@router.get("/flows/{flow_path:path}/runs")
def list_flow_runs(
    flow_path: str,
    per_page: int = 50,
    page: int = 1,
    windmill: WindmillClient = Depends(get_windmill_client),
) -> List[Dict[str, Any]]:
    try:
        runs = windmill.list_flow_runs(flow_path, per_page=per_page, page=page)
    except Exception as e:
        logger.warning(
            "windmill_flow_runs_failed",
            extra=log_extra(flow_path=flow_path, per_page=per_page, page=page, error=str(e)),
        )
        raise HTTPException(status_code=502, detail=f"Windmill error: {e}")
    logger.info(
        "windmill_flow_runs_listed",
        extra=log_extra(flow_path=flow_path, per_page=per_page, page=page, result_count=len(runs)),
    )
    return runs


@router.get("/flows/{flow_path:path}")
def get_flow(
    flow_path: str,
    windmill: WindmillClient = Depends(get_windmill_client),
) -> Dict[str, Any]:
    try:
        flow = windmill.get_flow(flow_path)
    except Exception as e:
        logger.warning("windmill_flow_load_failed", extra=log_extra(flow_path=flow_path, error=str(e)))
        raise HTTPException(status_code=502, detail=f"Windmill error: {e}")
    logger.info("windmill_flow_loaded", extra=log_extra(flow_path=flow_path))
    return {"path": flow.path, "name": flow.name, "summary": flow.summary, "schema": flow.schema}


@router.get("/jobs")
def list_jobs(
    per_page: int = 50,
    page: int = 1,
    job_kinds: Optional[str] = Query(None, description="Comma-separated: preview,script,dependencies,flow"),
    script_path_exact: Optional[str] = Query(None, description="Exact runnable path filter (script/flow)"),
    windmill: WindmillClient = Depends(get_windmill_client),
) -> List[Dict[str, Any]]:
    try:
        jobs = windmill.list_jobs(
            per_page=per_page,
            page=page,
            job_kinds=job_kinds,
            script_path_exact=script_path_exact,
        )
    except Exception as e:
        logger.warning(
            "windmill_jobs_list_failed",
            extra=log_extra(
                per_page=per_page,
                page=page,
                job_kinds=job_kinds,
                script_path_exact=script_path_exact,
                error=str(e),
            ),
        )
        raise HTTPException(status_code=502, detail=f"Windmill error: {e}")
    logger.info(
        "windmill_jobs_listed",
        extra=log_extra(
            per_page=per_page,
            page=page,
            job_kinds=job_kinds,
            script_path_exact=script_path_exact,
            result_count=len(jobs),
        ),
    )
    return jobs


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    windmill: WindmillClient = Depends(get_windmill_client),
) -> Dict[str, Any]:
    try:
        job = windmill.get_job(job_id)
    except Exception as e:
        logger.warning("windmill_job_load_failed", extra=log_extra(job_id=job_id, error=str(e)))
        raise HTTPException(status_code=502, detail=f"Windmill error: {e}")
    logger.info("windmill_job_loaded", extra=log_extra(job_id=job_id, status=job.status.value))
    return {
        "id": job.id,
        "status": job.status.value,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "finished_at": job.finished_at,
        "script_path": job.script_path,
        "job_kind": job.job_kind,
        "duration_ms": job.duration_ms,
        "result": job.result,
        "error": job.error,
    }


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: str,
    windmill: WindmillClient = Depends(get_windmill_client),
) -> Dict[str, Any]:
    try:
        logs = windmill.get_job_logs(job_id)
    except Exception as e:
        logger.warning("windmill_job_logs_failed", extra=log_extra(job_id=job_id, error=str(e)))
        raise HTTPException(status_code=502, detail=f"Windmill error: {e}")
    logger.info("windmill_job_logs_loaded", extra=log_extra(job_id=job_id, log_length=len(logs or "")))
    return {"job_id": job_id, "logs": logs}
