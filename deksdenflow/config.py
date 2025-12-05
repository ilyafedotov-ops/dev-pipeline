import os
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """
    Pydantic-backed configuration loaded from environment variables.

    Key env vars:
    - DEKSDENFLOW_DB_URL (preferred) or DEKSDENFLOW_DB_PATH for SQLite fallback.
    - DEKSDENFLOW_ENV (default: local)
    - DEKSDENFLOW_API_TOKEN (optional bearer token)
    - DEKSDENFLOW_REDIS_URL (queue backend; empty uses in-memory)
    - DEKSDENFLOW_LOG_LEVEL (default: INFO)
    - DEKSDENFLOW_WEBHOOK_TOKEN (optional shared secret)
    - PROTOCOL_*_MODEL (defaults for planning/decompose/exec/QA)
    - DEKSDENFLOW_MAX_TOKENS_PER_STEP / DEKSDENFLOW_MAX_TOKENS_PER_PROTOCOL (optional budgets)
    """

    db_url: Optional[str] = Field(default=None)
    db_path: Path = Field(default=Path(".deksdenflow.sqlite"))
    environment: str = Field(default="local")
    api_token: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)
    log_level: str = Field(default="INFO")
    webhook_token: Optional[str] = Field(default=None)

    planning_model: Optional[str] = Field(default=None)
    decompose_model: Optional[str] = Field(default=None)
    exec_model: Optional[str] = Field(default=None)
    qa_model: Optional[str] = Field(default=None)

    max_tokens_per_step: Optional[int] = Field(default=None)
    max_tokens_per_protocol: Optional[int] = Field(default=None)
    token_budget_mode: str = Field(default="strict")  # strict | warn | off

    class Config:
        arbitrary_types_allowed = True

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
    def is_postgres(self) -> bool:
        return bool(self.db_url and self.db_url.startswith("postgres"))


def load_config() -> Config:
    """
    Load orchestrator configuration from environment.
    """
    db_url = os.environ.get("DEKSDENFLOW_DB_URL")
    db_path = Path(os.environ.get("DEKSDENFLOW_DB_PATH", ".deksdenflow.sqlite")).expanduser()
    environment = os.environ.get("DEKSDENFLOW_ENV", "local")
    api_token = os.environ.get("DEKSDENFLOW_API_TOKEN")
    redis_url = os.environ.get("DEKSDENFLOW_REDIS_URL")
    log_level = os.environ.get("DEKSDENFLOW_LOG_LEVEL", "INFO")
    webhook_token = os.environ.get("DEKSDENFLOW_WEBHOOK_TOKEN")
    planning_model = os.environ.get("PROTOCOL_PLANNING_MODEL")
    decompose_model = os.environ.get("PROTOCOL_DECOMPOSE_MODEL")
    exec_model = os.environ.get("PROTOCOL_EXEC_MODEL")
    qa_model = os.environ.get("PROTOCOL_QA_MODEL")
    max_tokens_per_step = os.environ.get("DEKSDENFLOW_MAX_TOKENS_PER_STEP")
    max_tokens_per_protocol = os.environ.get("DEKSDENFLOW_MAX_TOKENS_PER_PROTOCOL")
    token_budget_mode = os.environ.get("DEKSDENFLOW_TOKEN_BUDGET_MODE", "strict")
    return Config(
        db_url=db_url,
        db_path=db_path,
        environment=environment,
        api_token=api_token,
        redis_url=redis_url,
        log_level=log_level,
        webhook_token=webhook_token,
        planning_model=planning_model,
        decompose_model=decompose_model,
        exec_model=exec_model,
        qa_model=qa_model,
        max_tokens_per_step=int(max_tokens_per_step) if max_tokens_per_step else None,
        max_tokens_per_protocol=int(max_tokens_per_protocol) if max_tokens_per_protocol else None,
        token_budget_mode=token_budget_mode,
    )
