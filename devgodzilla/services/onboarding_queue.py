from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.base import ServiceContext
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

logger = get_logger(__name__)


@dataclass(frozen=True)
class OnboardingEnqueueResult:
    run_id: str
    windmill_job_id: str
    script_path: str


def _build_windmill_client(ctx: ServiceContext) -> WindmillClient:
    config = ctx.config
    if not getattr(config, "windmill_enabled", False):
        raise RuntimeError("Windmill integration not configured")

    wm_config = WindmillConfig(
        base_url=config.windmill_url or "http://localhost:8000",
        token=config.windmill_token or "",
        workspace=getattr(config, "windmill_workspace", "devgodzilla"),
    )
    return WindmillClient(wm_config)


def enqueue_project_onboarding(
    ctx: ServiceContext,
    db: Database,
    *,
    project_id: int,
    branch: Optional[str] = None,
    run_discovery_agent: bool = True,
    discovery_pipeline: bool = True,
    discovery_engine_id: Optional[str] = None,
    discovery_model: Optional[str] = None,
    clone_if_missing: bool = True,
) -> OnboardingEnqueueResult:
    script_path = "u/devgodzilla/project_onboard_api"
    payload: dict[str, Any] = {
        "project_id": project_id,
        "run_discovery_agent": bool(run_discovery_agent),
        "discovery_pipeline": bool(discovery_pipeline),
        "clone_if_missing": bool(clone_if_missing),
    }
    if branch:
        payload["branch"] = branch
    if discovery_engine_id:
        payload["discovery_engine_id"] = discovery_engine_id
    if discovery_model:
        payload["discovery_model"] = discovery_model

    client = _build_windmill_client(ctx)
    try:
        logger.debug(
            "onboarding_enqueue_request",
            extra=log_extra(
                project_id=project_id,
                script_path=script_path,
                payload=payload,
                workspace=ctx.config.windmill_workspace,
            ),
        )
        enqueue_start = time.perf_counter()
        try:
            job_id = client.run_script(script_path, payload)
        except Exception as exc:
            logger.error(
                "onboarding_enqueue_failed",
                extra=log_extra(
                    project_id=project_id,
                    script_path=script_path,
                    error=str(exc),
                ),
            )
            raise
        enqueue_duration_ms = int((time.perf_counter() - enqueue_start) * 1000)
    finally:
        client.close()
    logger.info(
        "onboarding_enqueue_response",
        extra=log_extra(
            project_id=project_id,
            script_path=script_path,
            windmill_job_id=job_id,
            duration_ms=enqueue_duration_ms,
        ),
    )

    run_id = str(uuid4())
    db.create_job_run(
        run_id=run_id,
        job_type="onboarding",
        status="queued",
        run_kind="windmill_script",
        project_id=project_id,
        queue="windmill",
        params=payload,
        windmill_job_id=job_id,
    )
    try:
        db.append_event(
            protocol_run_id=None,
            project_id=project_id,
            event_type="onboarding_enqueued",
            message=f"Onboarding queued (job {job_id})",
            metadata={"windmill_job_id": job_id, "script_path": script_path},
        )
    except Exception:
        pass

    logger.info(
        "onboarding_enqueued",
        extra={"project_id": project_id, "windmill_job_id": job_id},
    )
    return OnboardingEnqueueResult(run_id=run_id, windmill_job_id=job_id, script_path=script_path)
