from typing import Optional

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str = "ok"


class ProjectCreate(BaseModel):
    name: str
    git_url: str
    local_path: Optional[str] = None
    base_branch: str = "main"
    ci_provider: Optional[str] = None
    default_models: Optional[dict] = None
    secrets: Optional[dict] = None


class ProjectOut(ProjectCreate):
    id: int
    created_at: str
    updated_at: str


class BranchListResponse(BaseModel):
    branches: list[str]


class BranchDeleteRequest(BaseModel):
    confirm: bool = False


class ProtocolRunCreate(BaseModel):
    protocol_name: str
    status: str = "pending"
    base_branch: str = "main"
    worktree_path: Optional[str] = None
    protocol_root: Optional[str] = None
    description: Optional[str] = None
    template_config: Optional[dict] = None
    template_source: Optional[dict] = None


class ProtocolRunOut(ProtocolRunCreate):
    id: int
    project_id: int
    created_at: str
    updated_at: str
    spec_hash: Optional[str] = None
    spec_validation_status: Optional[str] = None
    spec_validated_at: Optional[str] = None


class ProtocolSpecOut(BaseModel):
    protocol_run_id: int
    protocol_name: str
    project_id: int
    spec: Optional[dict] = None
    spec_hash: Optional[str] = None
    validation_status: Optional[str] = None
    validation_errors: Optional[list[str]] = None
    validated_at: Optional[str] = None


class StepRunCreate(BaseModel):
    step_index: int = Field(..., ge=0)
    step_name: str
    step_type: str
    status: str = "pending"
    model: Optional[str] = None
    summary: Optional[str] = None
    engine_id: Optional[str] = None
    policy: Optional[list[dict] | dict] = None


class StepRunOut(StepRunCreate):
    id: int
    protocol_run_id: int
    retries: int
    runtime_state: Optional[dict] = None
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
    protocol_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None


class CodexRunCreate(BaseModel):
    job_type: str
    prompt_version: Optional[str] = None
    params: Optional[dict] = None
    run_id: Optional[str] = None
    log_path: Optional[str] = None
    cost_tokens: Optional[int] = None
    cost_cents: Optional[int] = None


class CodexRunOut(BaseModel):
    run_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    prompt_version: Optional[str] = None
    params: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    log_path: Optional[str] = None
    cost_tokens: Optional[int] = None
    cost_cents: Optional[int] = None


class ActionResponse(BaseModel):
    message: str
    job: Optional[dict] = None


class OnboardingStartRequest(BaseModel):
    inline: bool = False


class OnboardingStage(BaseModel):
    key: str
    name: str
    status: str
    event_type: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[dict] = None


class OnboardingSummary(BaseModel):
    project_id: int
    protocol_run_id: Optional[int]
    status: str
    workspace_path: Optional[str] = None
    hint: Optional[str] = None
    last_event: Optional[EventOut] = None
    stages: list[OnboardingStage] = []
    events: list[EventOut] = []


class CodeMachineImportRequest(BaseModel):
    protocol_name: str
    workspace_path: str
    base_branch: str = "main"
    description: Optional[str] = None
    enqueue: bool = False


class CodeMachineImportResponse(BaseModel):
    protocol_run: ProtocolRunOut
    message: str
    job: Optional[dict] = None


class SpecAuditRequest(BaseModel):
    project_id: Optional[int] = None
    protocol_id: Optional[int] = None
    backfill: bool = False
    interval_seconds: Optional[int] = None  # override per-request if needed
