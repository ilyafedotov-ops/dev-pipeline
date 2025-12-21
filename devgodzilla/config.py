"""
DevGodzilla Configuration

Pydantic-backed configuration loaded from environment variables.
Uses DEVGODZILLA_ prefix for all environment variables.
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    """
    Pydantic-backed configuration loaded from environment variables.

    Key env vars:
    - DEVGODZILLA_DB_URL (preferred) or DEVGODZILLA_DB_PATH for SQLite fallback.
    - DEVGODZILLA_ENV (default: local)
    - DEVGODZILLA_API_TOKEN (optional bearer token)
    - DEVGODZILLA_LOG_LEVEL (default: INFO)
    - DEVGODZILLA_WEBHOOK_TOKEN (optional shared secret)
    - DEVGODZILLA_DEFAULT_ENGINE_ID (default: opencode)
    - DEVGODZILLA_DISCOVERY_ENGINE_ID / PLANNING_ENGINE_ID / EXEC_ENGINE_ID / QA_ENGINE_ID
    """

    # Database
    db_url: Optional[str] = Field(default=None)
    db_path: Path = Field(default=Path(".devgodzilla.sqlite"))
    db_pool_size: int = Field(default=5)
    
    # Environment
    environment: str = Field(default="local")
    api_token: Optional[str] = Field(default=None)
    log_level: str = Field(default="INFO")
    webhook_token: Optional[str] = Field(default=None)
    
    # JWT / local auth
    jwt_secret: Optional[str] = Field(default=None)
    jwt_issuer: str = Field(default="devgodzilla")
    jwt_access_ttl_seconds: int = Field(default=60 * 15)  # 15m
    jwt_refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 14)  # 14d
    jwt_refresh_rotate: bool = Field(default=True)
    admin_username: Optional[str] = Field(default=None)
    admin_password: Optional[str] = Field(default=None)  # dev-only fallback
    admin_password_hash: Optional[str] = Field(default=None)  # preferred (pbkdf2_sha256$...)
    
    # OIDC / SSO
    oidc_issuer: Optional[str] = Field(default=None)
    oidc_client_id: Optional[str] = Field(default=None)
    oidc_client_secret: Optional[str] = Field(default=None)
    oidc_scopes: str = Field(default="openid profile email")
    session_secret: Optional[str] = Field(default=None)
    session_cookie_secure: bool = Field(default=False)

    # Model defaults per stage
    planning_model: Optional[str] = Field(default=None)
    decompose_model: Optional[str] = Field(default=None)
    exec_model: Optional[str] = Field(default=None)
    qa_model: Optional[str] = Field(default=None)
    
    # Engine defaults
    default_engine_id: str = Field(default="opencode")
    discovery_engine_id: Optional[str] = Field(default=None)
    planning_engine_id: Optional[str] = Field(default=None)
    exec_engine_id: Optional[str] = Field(default=None)
    qa_engine_id: Optional[str] = Field(default=None)
    agent_config_path: Optional[Path] = Field(default=None)

    # Token budgets
    max_tokens_per_step: Optional[int] = Field(default=None)
    max_tokens_per_protocol: Optional[int] = Field(default=None)
    token_budget_mode: str = Field(default="strict")  # strict | warn | off
    
    # QA settings
    auto_qa_on_ci: bool = Field(default=False)
    auto_qa_after_exec: bool = Field(default=False)
    qa_auto_fix_enabled: bool = Field(default=True)
    qa_max_auto_fix_attempts: int = Field(default=3)
    
    # Git settings
    git_lock_max_retries: int = Field(default=5)
    git_lock_retry_delay: float = Field(default=1.0)
    
    # Misc
    spec_audit_interval_seconds: Optional[int] = Field(default=None)
    skip_simple_decompose: bool = Field(default=False)

    # API / web
    cors_allow_origins: List[str] = Field(default_factory=list)
    
    # Windmill integration
    windmill_url: Optional[str] = Field(default=None)
    windmill_token: Optional[str] = Field(default=None)
    windmill_workspace: str = Field(default="devgodzilla")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def default_models(self) -> Dict[str, str]:
        """Return model defaults per stage."""
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
        """Check if using PostgreSQL database."""
        return bool(self.db_url and self.db_url.startswith("postgres"))

    @property
    def oidc_enabled(self) -> bool:
        """Check if OIDC/SSO is enabled."""
        return bool(self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret)

    @property
    def jwt_enabled(self) -> bool:
        """Check if JWT auth is enabled."""
        return bool(self.jwt_secret and self.admin_username and (self.admin_password_hash or self.admin_password))
    
    @property
    def windmill_enabled(self) -> bool:
        """Check if Windmill integration is enabled."""
        return bool(self.windmill_url and self.windmill_token)


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse boolean from environment variable."""
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if value.strip() == "*":
        return ["*"]
    return [v.strip() for v in value.split(",") if v.strip()]


def _read_simple_env_file(path: Path) -> Dict[str, str]:
    """
    Read a simple KEY=VALUE env file.

    Supports:
    - blank lines and comments (# ...)
    - optional "export " prefix
    - quoted values ("..." or '...')
    """
    data: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return data

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]
        if key:
            data[key] = value
    return data


def _maybe_load_windmill_env_defaults() -> None:
    """
    Populate DEVGODZILLA_WINDMILL_* from a local env file.

    This is a convenience for local/dev setups where Windmill is already running and
    tokens live in a Windmill app env file.
    """
    candidates: list[Path] = []
    explicit = os.environ.get("DEVGODZILLA_WINDMILL_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            Path("windmill/apps/devgodzilla-react-app/.env.development"),
            Path(".env.development"),
        ]
    )

    env: Dict[str, str] = {}
    for candidate in candidates:
        if candidate.exists():
            env = _read_simple_env_file(candidate)
            if env:
                break

    if not env:
        return

    if not os.environ.get("DEVGODZILLA_WINDMILL_TOKEN"):
        token = env.get("DEVGODZILLA_WINDMILL_TOKEN") or env.get("WINDMILL_TOKEN") or env.get("VITE_TOKEN")
        if token:
            os.environ["DEVGODZILLA_WINDMILL_TOKEN"] = token

    if not os.environ.get("DEVGODZILLA_WINDMILL_WORKSPACE"):
        workspace = env.get("DEVGODZILLA_WINDMILL_WORKSPACE") or env.get("VITE_WORKSPACE")
        if workspace:
            os.environ["DEVGODZILLA_WINDMILL_WORKSPACE"] = workspace

    if not os.environ.get("DEVGODZILLA_WINDMILL_URL"):
        url = env.get("DEVGODZILLA_WINDMILL_URL") or env.get("WINDMILL_URL") or env.get("VITE_API_URL")
        if url:
            normalized = url.strip().rstrip("/")
            if normalized.endswith("/api"):
                normalized = normalized[: -len("/api")]
            os.environ["DEVGODZILLA_WINDMILL_URL"] = normalized


def load_config() -> Config:
    """
    Load DevGodzilla configuration from environment.
    
    Environment variables use the DEVGODZILLA_ prefix.
    Also supports DEVGODZILLA_CONFIG env var pointing to a config file (future).
    """
    _maybe_load_windmill_env_defaults()
    env = os.environ.get("DEVGODZILLA_ENV", "local")
    cors = _parse_csv(os.environ.get("DEVGODZILLA_CORS_ORIGINS"))
    if not cors and env == "local":
        cors = ["*"]
    return Config(
        # Database
        db_url=os.environ.get("DEVGODZILLA_DB_URL"),
        db_path=Path(os.environ.get("DEVGODZILLA_DB_PATH", ".devgodzilla.sqlite")).expanduser(),
        db_pool_size=int(os.environ.get("DEVGODZILLA_DB_POOL_SIZE", "5")),
        
        # Environment
        environment=env,
        api_token=os.environ.get("DEVGODZILLA_API_TOKEN"),
        log_level=os.environ.get("DEVGODZILLA_LOG_LEVEL", "INFO"),
        webhook_token=os.environ.get("DEVGODZILLA_WEBHOOK_TOKEN"),
        
        # JWT
        jwt_secret=os.environ.get("DEVGODZILLA_JWT_SECRET"),
        jwt_issuer=os.environ.get("DEVGODZILLA_JWT_ISSUER", "devgodzilla"),
        jwt_access_ttl_seconds=int(os.environ.get("DEVGODZILLA_JWT_ACCESS_TTL_SECONDS", str(60 * 15))),
        jwt_refresh_ttl_seconds=int(os.environ.get("DEVGODZILLA_JWT_REFRESH_TTL_SECONDS", str(60 * 60 * 24 * 14))),
        jwt_refresh_rotate=_parse_bool(os.environ.get("DEVGODZILLA_JWT_REFRESH_ROTATE"), default=True),
        admin_username=os.environ.get("DEVGODZILLA_ADMIN_USERNAME"),
        admin_password=os.environ.get("DEVGODZILLA_ADMIN_PASSWORD"),
        admin_password_hash=os.environ.get("DEVGODZILLA_ADMIN_PASSWORD_HASH"),
        
        # OIDC
        oidc_issuer=os.environ.get("DEVGODZILLA_OIDC_ISSUER"),
        oidc_client_id=os.environ.get("DEVGODZILLA_OIDC_CLIENT_ID"),
        oidc_client_secret=os.environ.get("DEVGODZILLA_OIDC_CLIENT_SECRET"),
        oidc_scopes=os.environ.get("DEVGODZILLA_OIDC_SCOPES", "openid profile email"),
        session_secret=os.environ.get("DEVGODZILLA_SESSION_SECRET"),
        session_cookie_secure=_parse_bool(os.environ.get("DEVGODZILLA_SESSION_COOKIE_SECURE")),
        
        # Models
        planning_model=os.environ.get("DEVGODZILLA_PLANNING_MODEL"),
        decompose_model=os.environ.get("DEVGODZILLA_DECOMPOSE_MODEL"),
        exec_model=os.environ.get("DEVGODZILLA_EXEC_MODEL"),
        qa_model=os.environ.get("DEVGODZILLA_QA_MODEL"),
        
        # Engines
        default_engine_id=os.environ.get("DEVGODZILLA_DEFAULT_ENGINE_ID", "opencode"),
        discovery_engine_id=os.environ.get("DEVGODZILLA_DISCOVERY_ENGINE_ID") or None,
        planning_engine_id=os.environ.get("DEVGODZILLA_PLANNING_ENGINE_ID") or None,
        exec_engine_id=os.environ.get("DEVGODZILLA_EXEC_ENGINE_ID") or None,
        qa_engine_id=os.environ.get("DEVGODZILLA_QA_ENGINE_ID") or None,
        agent_config_path=Path(os.environ.get("DEVGODZILLA_AGENT_CONFIG_PATH")) if os.environ.get("DEVGODZILLA_AGENT_CONFIG_PATH") else Path("config/agents.yaml"),
        
        # Token budgets
        max_tokens_per_step=int(v) if (v := os.environ.get("DEVGODZILLA_MAX_TOKENS_PER_STEP")) else None,
        max_tokens_per_protocol=int(v) if (v := os.environ.get("DEVGODZILLA_MAX_TOKENS_PER_PROTOCOL")) else None,
        token_budget_mode=os.environ.get("DEVGODZILLA_TOKEN_BUDGET_MODE", "strict"),
        
        # QA
        auto_qa_on_ci=_parse_bool(os.environ.get("DEVGODZILLA_AUTO_QA_ON_CI")),
        auto_qa_after_exec=_parse_bool(os.environ.get("DEVGODZILLA_AUTO_QA_AFTER_EXEC")),
        qa_auto_fix_enabled=_parse_bool(os.environ.get("DEVGODZILLA_QA_AUTO_FIX_ENABLED"), default=True),
        qa_max_auto_fix_attempts=int(os.environ.get("DEVGODZILLA_QA_MAX_AUTO_FIX_ATTEMPTS", "3")),
        
        # Git
        git_lock_max_retries=int(os.environ.get("DEVGODZILLA_GIT_LOCK_MAX_RETRIES", "5")),
        git_lock_retry_delay=float(os.environ.get("DEVGODZILLA_GIT_LOCK_RETRY_DELAY", "1.0")),
        
        # Misc
        spec_audit_interval_seconds=int(v) if (v := os.environ.get("DEVGODZILLA_SPEC_AUDIT_INTERVAL_SECONDS")) else None,
        skip_simple_decompose=_parse_bool(os.environ.get("DEVGODZILLA_SKIP_SIMPLE_DECOMPOSE")),

        # API / web
        cors_allow_origins=cors,
        
        # Windmill
        windmill_url=os.environ.get("DEVGODZILLA_WINDMILL_URL"),
        windmill_token=os.environ.get("DEVGODZILLA_WINDMILL_TOKEN"),
        windmill_workspace=os.environ.get("DEVGODZILLA_WINDMILL_WORKSPACE", "devgodzilla"),
    )


# Singleton config instance (lazy loaded)
_config: Optional[Config] = None
_config_lock = threading.Lock()


def get_config() -> Config:
    """Get or create the singleton config instance."""
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = load_config()
    return _config


def _reset_config_for_tests() -> None:
    """Reset the global config cache (tests only)."""
    global _config
    with _config_lock:
        _config = None
