from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

# =============================================================================
# Enums
# =============================================================================

class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class ProtocolStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"

# =============================================================================
# Base Models
# =============================================================================

class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class Health(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    service: str = "devgodzilla"

# =============================================================================
# Project Models
# =============================================================================

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    git_url: Optional[str] = None
    local_path: Optional[str] = None
    base_branch: str = "main"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    git_url: Optional[str] = None
    base_branch: Optional[str] = None
    local_path: Optional[str] = None

class ProjectOut(APIModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    git_url: Optional[str]
    base_branch: str = "main"
    local_path: Optional[str]
    created_at: Any
    updated_at: Any
    constitution_version: Optional[str] = None
    # Policy fields
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_overrides: Optional[Dict[str, Any]] = None
    policy_repo_local_enabled: Optional[bool] = None
    policy_effective_hash: Optional[str] = None
    policy_enforcement_mode: Optional[str] = None

class OnboardingStage(BaseModel):
    name: str
    status: str  # pending, running, completed, failed, skipped
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None

class OnboardingEvent(BaseModel):
    event_type: str
    message: str
    created_at: Any

class OnboardingSummary(BaseModel):
    project_id: int
    status: str
    stages: List[OnboardingStage]
    events: List[OnboardingEvent]
    blocking_clarifications: int

# =============================================================================
# Protocol Models
# =============================================================================

class ProtocolCreate(BaseModel):
    project_id: int
    name: str = Field(..., description="Name of the protocol run")
    description: Optional[str] = None
    branch_name: Optional[str] = None
    template: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None

class ProtocolAction(str, Enum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"

class ProtocolActionRequest(BaseModel):
    action: ProtocolAction
    reason: Optional[str] = None

class ProtocolOut(APIModel):
    id: int
    project_id: int
    protocol_name: str
    status: str
    base_branch: str
    worktree_path: Optional[str]
    summary: Optional[str] = None
    windmill_flow_id: Optional[str]
    speckit_metadata: Optional[Dict[str, Any]]
    created_at: Any
    updated_at: Any

class FeedbackRequest(BaseModel):
    action: str
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Step Models
# =============================================================================

class StepOut(APIModel):
    id: int
    protocol_run_id: int
    step_index: int
    step_name: str
    step_type: str
    status: str
    retries: int = 0
    model: Optional[str] = None
    engine_id: Optional[str] = None
    policy: Optional[Dict[str, Any]] = None
    runtime_state: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    assigned_agent: Optional[str]
    depends_on: Optional[List[int]] = None
    parallel_group: Optional[str] = None
    created_at: Any
    updated_at: Any

class StepAction(str, Enum):
    EXECUTE = "execute"
    RETRY = "retry"
    SKIP = "skip"

class StepActionRequest(BaseModel):
    action: StepAction
    force: bool = False

# =============================================================================
# Agent Models
# =============================================================================

class AgentInfo(BaseModel):
    id: str
    name: str
    kind: str
    capabilities: List[str]
    status: str = "available"
    default_model: Optional[str] = None
    command_dir: Optional[str] = None

class AgentConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    default_model: Optional[str] = None
    capabilities: Optional[List[str]] = None
    command_dir: Optional[str] = None

# =============================================================================
# Clarification Models
# =============================================================================

class ClarificationAnswer(BaseModel):
    answer: str
    answered_by: Optional[str] = None

class ClarificationOut(APIModel):
    id: int
    scope: Optional[str] = None
    project_id: Optional[int] = None
    protocol_run_id: Optional[int]
    step_run_id: Optional[int] = None
    key: Optional[str] = None
    question: str
    status: str
    options: Optional[List[str]] = None
    recommended: Optional[Dict[str, Any]] = None
    applies_to: Optional[str] = None
    blocking: Optional[bool] = None
    answer: Optional[Dict[str, Any]]
    created_at: Any
    answered_at: Optional[Any]
    answered_by: Optional[str] = None

# =============================================================================
# QA Models
# =============================================================================

class QAFindingOut(BaseModel):
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    rule_id: Optional[str] = None
    suggestion: Optional[str] = None

class QAGateOut(BaseModel):
    id: str
    name: str
    status: str  # passed|warning|failed|skipped
    findings: List[QAFindingOut] = Field(default_factory=list)

class QAResultOut(BaseModel):
    verdict: str  # passed|warning|failed
    summary: Optional[str] = None
    gates: List[QAGateOut] = Field(default_factory=list)

# =============================================================================
# Events
# =============================================================================


class EventOut(APIModel):
    id: int
    protocol_run_id: int
    step_run_id: Optional[int] = None
    event_type: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Any

# =============================================================================
# Artifact Models
# =============================================================================

class ArtifactOut(BaseModel):
    id: str
    type: str  # log|diff|file|report|json|text|unknown
    name: str
    size: int
    created_at: Optional[str] = None

class ArtifactContentOut(BaseModel):
    id: str
    name: str
    type: str
    content: str
    truncated: bool = False


class ProtocolArtifactOut(ArtifactOut):
    step_run_id: int
    step_name: Optional[str] = None


# =============================================================================
# Job Runs / Run Registry Models
# =============================================================================


class JobRunOut(APIModel):
    run_id: str
    job_type: str
    status: str
    run_kind: Optional[str] = None
    project_id: Optional[int] = None
    protocol_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    queue: Optional[str] = None
    attempt: Optional[int] = None
    worker_id: Optional[str] = None
    started_at: Optional[Any] = None
    finished_at: Optional[Any] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    log_path: Optional[str] = None
    cost_tokens: Optional[int] = None
    cost_cents: Optional[int] = None
    windmill_job_id: Optional[str] = None
    created_at: Any
    updated_at: Any


class RunArtifactOut(ArtifactOut):
    run_id: str

# =============================================================================
# Queue Models
# =============================================================================

class QueueStatsOut(BaseModel):
    name: str
    queued: int
    started: int
    failed: int

class QueueJobOut(BaseModel):
    job_id: str
    job_type: str
    status: str
    enqueued_at: Any
    started_at: Optional[Any] = None
    payload: Optional[Dict[str, Any]] = None

# =============================================================================
# Policy Models
# =============================================================================

class PolicyConfigOut(BaseModel):
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_overrides: Optional[Dict[str, Any]] = None
    policy_repo_local_enabled: bool = False
    policy_enforcement_mode: str = "warn"

class PolicyConfigUpdate(BaseModel):
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_overrides: Optional[Dict[str, Any]] = None
    policy_repo_local_enabled: Optional[bool] = None
    policy_enforcement_mode: Optional[str] = None

class EffectivePolicyOut(BaseModel):
    hash: str
    policy: Dict[str, Any]
    pack_key: str
    pack_version: str

class PolicyFindingOut(BaseModel):
    code: str
    severity: str
    message: str
    scope: str
    location: Optional[str] = None
    suggested_fix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BranchOut(BaseModel):
    name: str
    sha: str
    is_remote: bool

# =============================================================================
# Workflow / UI Convenience Models (Windmill React app)
# =============================================================================

class NextStepOut(BaseModel):
    step_run_id: Optional[int] = None


class RetryStepOut(BaseModel):
    """Response for retry_latest action."""
    step_run_id: int
    step_name: str
    message: str
    retries: int


class GateFindingOut(BaseModel):
    code: str
    severity: str  # info|warning|error
    message: str
    step_id: Optional[str] = None
    suggested_fix: Optional[str] = None


class GateResultOut(BaseModel):
    article: str
    name: str
    status: str  # passed|warning|failed|skipped
    findings: List[GateFindingOut] = Field(default_factory=list)


class ChecklistItemOut(BaseModel):
    id: str
    description: str
    passed: bool
    required: bool


class ChecklistResultOut(BaseModel):
    passed: int
    total: int
    items: List[ChecklistItemOut] = Field(default_factory=list)


class QualitySummaryOut(BaseModel):
    protocol_run_id: int
    constitution_version: str = "1"
    score: float
    gates: List[GateResultOut] = Field(default_factory=list)
    checklist: ChecklistResultOut
    overall_status: str  # passed|warning|failed
    blocking_issues: int
    warnings: int


class FeedbackEventOut(BaseModel):
    id: str
    action_taken: str
    created_at: Any
    resolved: bool
    clarification: Optional[ClarificationOut] = None


class FeedbackListOut(BaseModel):
    events: List[FeedbackEventOut] = Field(default_factory=list)

# =============================================================================
# Agile Models
# =============================================================================

class SprintCreate(BaseModel):
    project_id: int
    name: str
    goal: Optional[str] = None
    status: str = "planning"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    velocity_planned: Optional[int] = None

class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    velocity_planned: Optional[int] = None
    velocity_actual: Optional[int] = None

class SprintOut(APIModel):
    id: int
    project_id: int
    name: str
    goal: Optional[str] = None
    status: str
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    velocity_planned: Optional[int] = None
    velocity_actual: Optional[int] = None
    created_at: Any
    updated_at: Any

class BurndownPointOut(BaseModel):
    date: str
    ideal: float
    actual: float

class SprintMetricsOut(BaseModel):
    sprint_id: int
    total_tasks: int
    completed_tasks: int
    total_points: int
    completed_points: int
    burndown: List[BurndownPointOut]
    velocity_trend: List[int]

class AgileTaskCreate(BaseModel):
    project_id: int
    title: str
    task_type: str = "story"
    priority: str = "medium"
    board_status: str = "backlog"
    sprint_id: Optional[int] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    story_points: Optional[int] = None
    due_date: Optional[datetime] = None
    labels: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    blocked_by: List[int] = Field(default_factory=list)
    blocks: List[int] = Field(default_factory=list)

class AgileTaskUpdate(BaseModel):
    title: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[str] = None
    board_status: Optional[str] = None
    sprint_id: Optional[int] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    story_points: Optional[int] = None
    due_date: Optional[datetime] = None
    labels: Optional[List[str]] = None
    acceptance_criteria: Optional[List[str]] = None
    blocked_by: Optional[List[int]] = None
    blocks: Optional[List[int]] = None

class AgileTaskOut(APIModel):
    id: int
    project_id: int
    sprint_id: Optional[int] = None
    protocol_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    task_type: str
    priority: str
    board_status: str
    story_points: Optional[int] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    blocked_by: List[int] = Field(default_factory=list)
    blocks: List[int] = Field(default_factory=list)
    due_date: Optional[Any] = None
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    created_at: Any
    updated_at: Any

# =============================================================================
# Policy Pack Models
# =============================================================================

class PolicyPackContent(BaseModel):
    meta: Optional[Dict[str, Any]] = None
    defaults: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    clarifications: Optional[List[Dict[str, Any]] | Dict[str, Any]] = None
    enforcement: Optional[Dict[str, Any]] = None

class PolicyPackCreate(BaseModel):
    key: str
    version: str
    name: str
    description: Optional[str] = None
    status: str = "active"
    pack: Dict[str, Any] = Field(default_factory=dict)

class PolicyPackOut(APIModel):
    id: int
    key: str
    version: str
    name: str
    description: Optional[str] = None
    status: str
    pack: Dict[str, Any]
    created_at: Any
    updated_at: Optional[Any] = None

# =============================================================================
# Sprint-Protocol Integration Schemas
# =============================================================================

class LinkProtocolRequest(BaseModel):
    protocol_run_id: int
    auto_sync: bool = True

class ImportTasksRequest(BaseModel):
    spec_path: str
    overwrite_existing: bool = False

class CreateSprintFromProtocolRequest(BaseModel):
    sprint_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    auto_sync: bool = True

class SprintVelocityOut(BaseModel):
    sprint_id: int
    velocity_actual: int
    total_points: int
    completed_points: int
    completion_rate: float

class SyncResult(BaseModel):
    sprint_id: int
    protocol_run_id: int
    tasks_synced: int
    task_ids: List[int]

class ExportTasksRequest(BaseModel):
    output_path: str

class ExportTasksResult(BaseModel):
    sprint_id: int
    output_path: str
    content_length: int
