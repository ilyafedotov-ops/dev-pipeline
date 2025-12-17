import os
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    """
    Pydantic-backed configuration loaded from environment variables.

    Key env vars:
    - TASKSGODZILLA_DB_URL (preferred) or TASKSGODZILLA_DB_PATH for SQLite fallback.
    - TASKSGODZILLA_ENV (default: local)
    - TASKSGODZILLA_API_TOKEN (optional bearer token)
    - TASKSGODZILLA_REDIS_URL (queue backend; required)
    - TASKSGODZILLA_INLINE_RQ_WORKER (optional; run a background RQ worker inside the API process for tests/dev)
    - TASKSGODZILLA_LOG_LEVEL (default: INFO)
    - TASKSGODZILLA_WEBHOOK_TOKEN (optional shared secret)
    - PROTOCOL_*_MODEL (defaults for planning/decompose/exec/QA)
    - TASKSGODZILLA_MAX_TOKENS_PER_STEP / TASKSGODZILLA_MAX_TOKENS_PER_PROTOCOL (optional budgets)
    - TASKSGODZILLA_DEFAULT_ENGINE_ID (default: opencode)
    - TASKSGODZILLA_DISCOVERY_ENGINE_ID / PLANNING_ENGINE_ID / EXEC_ENGINE_ID / QA_ENGINE_ID (per-stage overrides)
    """

    db_url: Optional[str] = Field(default=None)
    db_path: Path = Field(default=Path(".tasksgodzilla.sqlite"))
    environment: str = Field(default="local")
    api_token: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)
    log_level: str = Field(default="INFO")
    webhook_token: Optional[str] = Field(default=None)
    # JWT / local auth (optional; enables username/password login for the web console)
    jwt_secret: Optional[str] = Field(default=None)
    jwt_issuer: str = Field(default="tasksgodzilla")
    jwt_access_ttl_seconds: int = Field(default=60 * 15)  # 15m
    jwt_refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 14)  # 14d
    jwt_refresh_rotate: bool = Field(default=True)
    admin_username: Optional[str] = Field(default=None)
    admin_password: Optional[str] = Field(default=None)  # dev-only fallback
    admin_password_hash: Optional[str] = Field(default=None)  # preferred (pbkdf2_sha256$...)
    # OIDC / SSO (optional; enables cookie-based auth for the web console)
    oidc_issuer: Optional[str] = Field(default=None)
    oidc_client_id: Optional[str] = Field(default=None)
    oidc_client_secret: Optional[str] = Field(default=None)
    oidc_scopes: str = Field(default="openid profile email")
    session_secret: Optional[str] = Field(default=None)
    session_cookie_secure: bool = Field(default=False)

    planning_model: Optional[str] = Field(default=None)
    decompose_model: Optional[str] = Field(default=None)
    exec_model: Optional[str] = Field(default=None)
    qa_model: Optional[str] = Field(default=None)
    default_engine_id: str = Field(default="opencode")
    # Per-stage engine overrides (fall back to default_engine_id when None)
    discovery_engine_id: Optional[str] = Field(default=None)
    planning_engine_id: Optional[str] = Field(default=None)
    exec_engine_id: Optional[str] = Field(default=None)
    qa_engine_id: Optional[str] = Field(default=None)

    max_tokens_per_step: Optional[int] = Field(default=None)
    max_tokens_per_protocol: Optional[int] = Field(default=None)
    token_budget_mode: str = Field(default="strict")  # strict | warn | off
    db_pool_size: int = Field(default=5)
    auto_qa_on_ci: bool = Field(default=False)
    auto_qa_after_exec: bool = Field(default=False)
    spec_audit_interval_seconds: Optional[int] = Field(default=None)
    skip_simple_decompose: bool = Field(default=False)
    inline_rq_worker: bool = Field(default=False)
    qa_auto_fix_enabled: bool = Field(default=True)
    qa_max_auto_fix_attempts: int = Field(default=3)
    git_lock_max_retries: int = Field(default=5)
    git_lock_retry_delay: float = Field(default=1.0)
    # Optional Windmill integration for log/artifact proxying.
    windmill_url: Optional[str] = Field(default=None)
    windmill_token: Optional[str] = Field(default=None)
    windmill_workspace: str = Field(default="starter")
    windmill_timeout_seconds: float = Field(default=30.0)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def default_models(self) -> Dict[str, str]:
        models = {}
        if self.planning_model:
            models["planning"] = self.planning_model
        if self.decompose_model:
            models["decompose"] = self.decompose_model
        if self.exec_model:
            models["exec"] = self.exec_model
        if self.qa_model:
            models["qa"] = self.qa_model
        return models

    @property
    def engine_defaults(self) -> Dict[str, str]:
        """Return engine defaults per stage, falling back to default_engine_id."""
        base = self.default_engine_id
        return {
            "discovery": self.discovery_engine_id or base,
            "planning": self.planning_engine_id or base,
            "exec": self.exec_engine_id or base,
            "qa": self.qa_engine_id or base,
        }

    @property
    def is_postgres(self) -> bool:
        return bool(self.db_url and self.db_url.startswith("postgres"))

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret)

    @property
    def jwt_enabled(self) -> bool:
        return bool(self.jwt_secret and self.admin_username and (self.admin_password_hash or self.admin_password))


def load_config() -> Config:
    """
    Load orchestrator configuration from environment.
    """
    db_url = os.environ.get("TASKSGODZILLA_DB_URL")
    db_path = Path(os.environ.get("TASKSGODZILLA_DB_PATH", ".tasksgodzilla.sqlite")).expanduser()
    environment = os.environ.get("TASKSGODZILLA_ENV", "local")
    api_token = os.environ.get("TASKSGODZILLA_API_TOKEN")
    redis_url = os.environ.get("TASKSGODZILLA_REDIS_URL")
    log_level = os.environ.get("TASKSGODZILLA_LOG_LEVEL", "INFO")
    webhook_token = os.environ.get("TASKSGODZILLA_WEBHOOK_TOKEN")
    jwt_secret = os.environ.get("TASKSGODZILLA_JWT_SECRET")
    jwt_issuer = os.environ.get("TASKSGODZILLA_JWT_ISSUER", "tasksgodzilla")
    jwt_access_ttl_seconds = int(os.environ.get("TASKSGODZILLA_JWT_ACCESS_TTL_SECONDS", str(60 * 15)))
    jwt_refresh_ttl_seconds = int(os.environ.get("TASKSGODZILLA_JWT_REFRESH_TTL_SECONDS", str(60 * 60 * 24 * 14)))
    jwt_refresh_rotate = os.environ.get("TASKSGODZILLA_JWT_REFRESH_ROTATE", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    admin_username = os.environ.get("TASKSGODZILLA_ADMIN_USERNAME")
    admin_password = os.environ.get("TASKSGODZILLA_ADMIN_PASSWORD")
    admin_password_hash = os.environ.get("TASKSGODZILLA_ADMIN_PASSWORD_HASH")
    oidc_issuer = os.environ.get("TASKSGODZILLA_OIDC_ISSUER")
    oidc_client_id = os.environ.get("TASKSGODZILLA_OIDC_CLIENT_ID")
    oidc_client_secret = os.environ.get("TASKSGODZILLA_OIDC_CLIENT_SECRET")
    oidc_scopes = os.environ.get("TASKSGODZILLA_OIDC_SCOPES", "openid profile email")
    session_secret = os.environ.get("TASKSGODZILLA_SESSION_SECRET")
    session_cookie_secure = os.environ.get("TASKSGODZILLA_SESSION_COOKIE_SECURE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    planning_model = os.environ.get("PROTOCOL_PLANNING_MODEL")
    decompose_model = os.environ.get("PROTOCOL_DECOMPOSE_MODEL")
    exec_model = os.environ.get("PROTOCOL_EXEC_MODEL")
    qa_model = os.environ.get("PROTOCOL_QA_MODEL")
    default_engine_id = os.environ.get("TASKSGODZILLA_DEFAULT_ENGINE_ID", "opencode")
    # Per-stage engine overrides (Optional[str] - None means use default_engine_id)
    discovery_engine_id = os.environ.get("TASKSGODZILLA_DISCOVERY_ENGINE_ID") or None
    planning_engine_id = os.environ.get("TASKSGODZILLA_PLANNING_ENGINE_ID") or None
    exec_engine_id = os.environ.get("TASKSGODZILLA_EXEC_ENGINE_ID") or None
    qa_engine_id = os.environ.get("TASKSGODZILLA_QA_ENGINE_ID") or None
    max_tokens_per_step = os.environ.get("TASKSGODZILLA_MAX_TOKENS_PER_STEP")
    max_tokens_per_protocol = os.environ.get("TASKSGODZILLA_MAX_TOKENS_PER_PROTOCOL")
    token_budget_mode = os.environ.get("TASKSGODZILLA_TOKEN_BUDGET_MODE", "strict")
    db_pool_size = int(os.environ.get("TASKSGODZILLA_DB_POOL_SIZE", "5"))
    spec_audit_interval_seconds = os.environ.get("TASKSGODZILLA_SPEC_AUDIT_INTERVAL_SECONDS")
    skip_simple_decompose = os.environ.get("PROTOCOL_SKIP_SIMPLE_DECOMPOSE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    auto_qa_on_ci = os.environ.get("TASKSGODZILLA_AUTO_QA_ON_CI", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    auto_qa_after_exec = os.environ.get("TASKSGODZILLA_AUTO_QA_AFTER_EXEC", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    inline_rq_worker = os.environ.get("TASKSGODZILLA_INLINE_RQ_WORKER", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    qa_auto_fix_enabled = os.environ.get("TASKSGODZILLA_QA_AUTO_FIX_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    qa_max_auto_fix_attempts = int(os.environ.get("TASKSGODZILLA_QA_MAX_AUTO_FIX_ATTEMPTS", "3"))
    git_lock_max_retries = int(os.environ.get("TASKSGODZILLA_GIT_LOCK_MAX_RETRIES", "5"))
    git_lock_retry_delay = float(os.environ.get("TASKSGODZILLA_GIT_LOCK_RETRY_DELAY", "1.0"))
    windmill_url = os.environ.get("TASKSGODZILLA_WINDMILL_URL")
    windmill_token = os.environ.get("TASKSGODZILLA_WINDMILL_TOKEN")
    windmill_workspace = os.environ.get("TASKSGODZILLA_WINDMILL_WORKSPACE", "starter")
    windmill_timeout_seconds = float(os.environ.get("TASKSGODZILLA_WINDMILL_TIMEOUT_SECONDS", "30"))
    return Config(
        db_url=db_url,
        db_path=db_path,
        environment=environment,
        api_token=api_token,
        redis_url=redis_url,
        log_level=log_level,
        webhook_token=webhook_token,
        jwt_secret=jwt_secret,
        jwt_issuer=jwt_issuer,
        jwt_access_ttl_seconds=jwt_access_ttl_seconds,
        jwt_refresh_ttl_seconds=jwt_refresh_ttl_seconds,
        jwt_refresh_rotate=jwt_refresh_rotate,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_password_hash=admin_password_hash,
        oidc_issuer=oidc_issuer,
        oidc_client_id=oidc_client_id,
        oidc_client_secret=oidc_client_secret,
        oidc_scopes=oidc_scopes,
        session_secret=session_secret,
        session_cookie_secure=session_cookie_secure,
        planning_model=planning_model,
        decompose_model=decompose_model,
        exec_model=exec_model,
        qa_model=qa_model,
        default_engine_id=default_engine_id,
        discovery_engine_id=discovery_engine_id,
        planning_engine_id=planning_engine_id,
        exec_engine_id=exec_engine_id,
        qa_engine_id=qa_engine_id,
        max_tokens_per_step=int(max_tokens_per_step) if max_tokens_per_step else None,
        max_tokens_per_protocol=int(max_tokens_per_protocol) if max_tokens_per_protocol else None,
        token_budget_mode=token_budget_mode,
        db_pool_size=db_pool_size,
        auto_qa_on_ci=auto_qa_on_ci,
        auto_qa_after_exec=auto_qa_after_exec,
        spec_audit_interval_seconds=int(spec_audit_interval_seconds) if spec_audit_interval_seconds else None,
        skip_simple_decompose=skip_simple_decompose,
        inline_rq_worker=inline_rq_worker,
        qa_auto_fix_enabled=qa_auto_fix_enabled,
        qa_max_auto_fix_attempts=qa_max_auto_fix_attempts,
        git_lock_max_retries=git_lock_max_retries,
        git_lock_retry_delay=git_lock_retry_delay,
        windmill_url=windmill_url,
        windmill_token=windmill_token,
        windmill_workspace=windmill_workspace,
        windmill_timeout_seconds=windmill_timeout_seconds,
    )
