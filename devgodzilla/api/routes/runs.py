from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from devgodzilla.api import schemas
from devgodzilla.api.run_context import enrich_run_with_agile_context, enrich_runs_with_agile_context
from devgodzilla.api.dependencies import get_db
from devgodzilla.config import load_config
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.windmill.client import JobStatus, WindmillClient, WindmillConfig

router = APIRouter(tags=["Runs"])
logger = get_logger(__name__)


def _build_windmill_client() -> WindmillClient | None:
    config = load_config()
    if not getattr(config, "windmill_enabled", False):
        return None
    try:
        wm_config = WindmillConfig(
            base_url=config.windmill_url or "http://localhost:8000",
            token=config.windmill_token or "",
            workspace=getattr(config, "windmill_workspace", "devgodzilla"),
        )
        return WindmillClient(wm_config)
    except Exception as exc:
        logger.warning("windmill_client_unavailable", extra={"error": str(exc)})
        return None


def _map_windmill_status(status: JobStatus) -> str:
    mapping = {
        JobStatus.QUEUED: "queued",
        JobStatus.RUNNING: "running",
        JobStatus.COMPLETED: "succeeded",
        JobStatus.FAILED: "failed",
        JobStatus.CANCELED: "cancelled",
    }
    return mapping.get(status, status.value)


def _sync_run_from_windmill(
    db: Database,
    run,
    windmill: WindmillClient | None,
):
    if not windmill or not run.windmill_job_id:
        return run
    if run.status not in ("queued", "running"):
        return run

    try:
        job = windmill.get_job(run.windmill_job_id)
    except Exception as exc:
        logger.warning(
            "windmill_job_sync_failed",
            extra={"windmill_job_id": run.windmill_job_id, "error": str(exc)},
        )
        return run

    updates: dict[str, object] = {}
    mapped_status = _map_windmill_status(job.status)
    if mapped_status != run.status:
        updates["status"] = mapped_status
    if job.started_at:
        updates["started_at"] = job.started_at
    if job.completed_at:
        updates["finished_at"] = job.completed_at
    if job.result is not None:
        updates["result"] = job.result
    if job.error:
        updates["error"] = job.error

    if updates:
        try:
            return db.update_job_run(run.run_id, **updates)
        except Exception as exc:
            logger.warning(
                "windmill_job_sync_update_failed",
                extra={"run_id": run.run_id, "error": str(exc)},
            )
    return run


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


def _log_chunk_to_sse(payload: dict, event_id: Optional[int] = None) -> str:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}event: log\ndata: {json.dumps(payload)}\n\n"


async def _log_stream(
    path: Optional[Path],
    *,
    since_bytes: int = 0,
    poll_interval_seconds: float = 0.5,
    max_chunk_bytes: int = 65536,
) -> AsyncGenerator[str, None]:
    offset = max(0, int(since_bytes))
    yield "event: connected\ndata: {}\n\n"

    idle_ticks = 0
    while True:
        if not path or not path.exists() or not path.is_file():
            idle_ticks += 1
        else:
            try:
                size = path.stat().st_size
                if size < offset:
                    offset = 0
                if size > offset:
                    idle_ticks = 0
                    with path.open("rb") as handle:
                        handle.seek(offset)
                        chunk = handle.read(max_chunk_bytes)
                    offset += len(chunk)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        payload = {"offset": offset, "chunk": text}
                        yield _log_chunk_to_sse(payload, event_id=offset)
                else:
                    idle_ticks += 1
            except Exception:
                idle_ticks += 1

        if idle_ticks >= int(30 / max(poll_interval_seconds, 0.1)):
            idle_ticks = 0
            yield ": heartbeat\n\n"

        await asyncio.sleep(poll_interval_seconds)


@router.get("/runs", response_model=List[schemas.JobRunOut])
def list_runs(
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    step_run_id: Optional[int] = None,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 200,
    db: Database = Depends(get_db),
):
    logger.info(
        "runs_list_requested",
        extra=log_extra(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            status=status,
            job_type=job_type,
            limit=limit,
        ),
    )
    runs = db.list_job_runs(
        limit=limit,
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        step_run_id=step_run_id,
        status=status,
        job_type=job_type,
    )
    windmill = _build_windmill_client()
    if windmill:
        try:
            synced = [_sync_run_from_windmill(db, run, windmill) for run in runs]
            if status:
                runs = [run for run in synced if run.status == status]
            else:
                runs = synced
        finally:
            windmill.close()
    enriched = [schemas.JobRunOut.model_validate(run) for run in enrich_runs_with_agile_context(db, runs)]
    logger.info(
        "runs_list_completed",
        extra=log_extra(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            status=status,
            job_type=job_type,
            result_count=len(enriched),
        ),
    )
    return enriched


@router.get("/runs/{run_id}", response_model=schemas.JobRunOut)
def get_run(
    run_id: str,
    db: Database = Depends(get_db),
):
    try:
        run = db.get_job_run(run_id)
    except KeyError:
        logger.warning("run_not_found", extra=log_extra(run_id=run_id))
        raise HTTPException(status_code=404, detail="Run not found")
    windmill = _build_windmill_client()
    if windmill:
        try:
            run = _sync_run_from_windmill(db, run, windmill)
        finally:
            windmill.close()
    enriched = schemas.JobRunOut.model_validate(enrich_run_with_agile_context(db, run))
    logger.info(
        "run_loaded",
        extra=log_extra(
            run_id=run.run_id,
            project_id=run.project_id,
            protocol_run_id=run.protocol_run_id,
            step_run_id=run.step_run_id,
            status=run.status,
            job_type=run.job_type,
        ),
    )
    return enriched


@router.get("/runs/{run_id}/logs", response_model=schemas.ArtifactContentOut)
def get_run_logs(
    run_id: str,
    max_bytes: int = 200_000,
    db: Database = Depends(get_db),
):
    try:
        run = db.get_job_run(run_id)
    except KeyError:
        logger.warning("run_logs_not_found", extra=log_extra(run_id=run_id))
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.log_path:
        logger.info("run_logs_missing_path", extra=log_extra(run_id=run.run_id))
        return schemas.ArtifactContentOut(
            id="logs",
            name="logs",
            type="log",
            content="",
            truncated=False,
        )

    path = Path(run.log_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists() or not path.is_file():
        logger.warning(
            "run_logs_file_missing",
            extra=log_extra(run_id=run.run_id, log_path=str(path)),
        )
        raise HTTPException(status_code=404, detail="Run logs not found")

    max_bytes = max(1, min(int(max_bytes), 2_000_000))
    raw = path.read_bytes()
    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]

    try:
        content = raw.decode("utf-8")
    except Exception:
        content = raw.decode("utf-8", errors="replace")

    logger.info(
        "run_logs_loaded",
        extra=log_extra(
            run_id=run.run_id,
            log_path=str(path),
            returned_bytes=len(raw),
            truncated=truncated,
        ),
    )

    return schemas.ArtifactContentOut(
        id="logs",
        name=path.name,
        type="log",
        content=content,
        truncated=truncated,
    )


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(
    run_id: str,
    since_bytes: int = Query(0, ge=0, description="Only stream bytes after this offset"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    poll_interval_seconds: float = Query(0.5, ge=0.1, le=5),
    max_chunk_bytes: int = Query(65536, ge=1024, le=200000),
    db: Database = Depends(get_db),
):
    try:
        run = db.get_job_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    path = Path(run.log_path).expanduser() if run.log_path else None
    if path and not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    effective_since = since_bytes
    if last_event_id and last_event_id.isdigit():
        effective_since = max(effective_since, int(last_event_id))

    return StreamingResponse(
        _log_stream(
            path,
            since_bytes=effective_since,
            poll_interval_seconds=poll_interval_seconds,
            max_chunk_bytes=max_chunk_bytes,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/runs/{run_id}/artifacts", response_model=List[schemas.RunArtifactOut])
def list_run_artifacts(
    run_id: str,
    db: Database = Depends(get_db),
):
    try:
        db.get_job_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    artifacts = db.list_run_artifacts(run_id)
    items: list[schemas.RunArtifactOut] = []
    for a in artifacts:
        size = 0
        try:
            p = Path(a.path).expanduser()
            size = p.stat().st_size if p.exists() else (a.bytes or 0)
        except Exception:
            size = a.bytes or 0

        items.append(
            schemas.RunArtifactOut(
                run_id=a.run_id,
                id=a.name,
                type=_artifact_type_from_name(a.name),
                name=a.name,
                size=int(size),
                created_at=None,
            )
        )
    return items


@router.get("/runs/{run_id}/artifacts/{artifact_id}/content", response_model=schemas.ArtifactContentOut)
def get_run_artifact_content(
    run_id: str,
    artifact_id: str,
    max_bytes: int = 200_000,
    db: Database = Depends(get_db),
):
    try:
        artifact = db.get_run_artifact(run_id, artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = Path(artifact.path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
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
