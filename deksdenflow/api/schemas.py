from typing import Optional

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str = "ok"


class ProjectCreate(BaseModel):
    name: str
    git_url: str
    base_branch: str = "main"
    ci_provider: Optional[str] = None
    default_models: Optional[dict] = None
    secrets: Optional[dict] = None


class ProjectOut(ProjectCreate):
    id: int
    created_at: str
    updated_at: str


class ProtocolRunCreate(BaseModel):
    protocol_name: str
    status: str = "pending"
    base_branch: str = "main"
    worktree_path: Optional[str] = None
    protocol_root: Optional[str] = None
    description: Optional[str] = None


class ProtocolRunOut(ProtocolRunCreate):
    id: int
    project_id: int
    created_at: str
    updated_at: str


class StepRunCreate(BaseModel):
    step_index: int = Field(..., ge=0)
    step_name: str
    step_type: str
    status: str = "pending"
    model: Optional[str] = None
    summary: Optional[str] = None


class StepRunOut(StepRunCreate):
    id: int
    protocol_run_id: int
    retries: int
    created_at: str
    updated_at: str


class EventOut(BaseModel):
    id: int
    protocol_run_id: int
    step_run_id: Optional[int]
    event_type: str
    message: str
    created_at: str
    metadata: Optional[dict] = None


class ActionResponse(BaseModel):
    message: str
    job: Optional[dict] = None
