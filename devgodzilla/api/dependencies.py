from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from devgodzilla.cli.main import get_db as cli_get_db, get_service_context as cli_get_service_context
from devgodzilla.services.base import ServiceContext

from devgodzilla.db.database import Database
from devgodzilla.windmill.client import WindmillClient, WindmillConfig
from devgodzilla.config import load_config

def get_db():
    """Get database instance."""
    db = cli_get_db()
    try:
        yield db
    finally:
        pass


def require_api_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_devgodzilla_token: Optional[str] = Header(None, alias="X-DevGodzilla-Token"),
) -> None:
    """
    Require an API bearer token if `DEVGODZILLA_API_TOKEN` is set.

    Accepted headers:
    - `Authorization: Bearer <token>`
    - `X-DevGodzilla-Token: <token>`
    """
    config = load_config()
    expected = config.api_token
    if not expected:
        return

    if x_devgodzilla_token and x_devgodzilla_token == expected:
        return

    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected:
            return

    raise HTTPException(status_code=401, detail="Unauthorized")


def require_webhook_token(
    request: Request,
    x_devgodzilla_webhook_token: Optional[str] = Header(None, alias="X-DevGodzilla-Webhook-Token"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature"),
    x_gitlab_token: Optional[str] = Header(None, alias="X-Gitlab-Token"),
) -> None:
    """
    Require a webhook token if `DEVGODZILLA_WEBHOOK_TOKEN` is set.

    This is intentionally separate from API auth so deployments can:
    - expose inbound webhooks to Windmill/CI, while
    - still securing the public API surface.
    """
    config = load_config()
    expected = config.webhook_token
    if not expected:
        return
    if x_devgodzilla_webhook_token == expected:
        return
    path = request.url.path or ""
    if path.endswith("/webhooks/github") or path.endswith("/webhooks/gitlab"):
        if x_hub_signature_256 or x_hub_signature or x_gitlab_token:
            return
    if x_devgodzilla_webhook_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

def get_service_context(
    _db: Database = Depends(get_db),
    x_project_id: Optional[int] = Header(None, alias="X-Project-ID")
) -> ServiceContext:
    """Get service context."""
    # Reuse the logic from CLI for now, but in a real API we might want 
    # request-scoped logging and context
    return cli_get_service_context(project_id=x_project_id)


def get_windmill_client(
    ctx: ServiceContext = Depends(get_service_context),
) -> WindmillClient:
    """Get a Windmill client from config (requires DEVGODZILLA_WINDMILL_*)."""
    config = ctx.config
    if not getattr(config, "windmill_enabled", False):
        raise HTTPException(status_code=503, detail="Windmill integration not configured")

    wm_config = WindmillConfig(
        base_url=config.windmill_url or "http://localhost:8000",
        token=config.windmill_token or "",
        workspace=getattr(config, "windmill_workspace", "devgodzilla"),
    )
    return WindmillClient(wm_config)
