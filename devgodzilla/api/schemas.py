from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_validator

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
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_QA = "needs_qa"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

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
    github_token: Optional[str] = None
    base_branch: str = "main"
    auto_onboard: bool = True
    auto_discovery: bool = True

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    git_url: Optional[str] = None
    base_branch: Optional[str] = None
    local_path: Optional[str] = None
    github_token: Optional[str] = None

class ProjectOut(APIModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    git_url: Optional[str]
    base_branch: str = "main"
    local_path: Optional[str]
    github_token_configured: bool = False
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
    id: int
    event_type: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Any

class OnboardingSummary(BaseModel):
    project_id: int
    status: str
    stages: List[OnboardingStage]
    events: List[OnboardingEvent]
    blocking_clarifications: int


class DiscoveryRetryRequest(BaseModel):
    discovery_pipeline: bool = True
    discovery_engine_id: Optional[str] = None
    discovery_model: Optional[str] = None
    stages: Optional[List[str]] = None
    strict_outputs: bool = True


class DiscoveryRetryResponse(BaseModel):
    success: bool
    discovery_log_path: Optional[str] = None
    discovery_missing_outputs: List[str] = Field(default_factory=list)
    discovery_error: Optional[str] = None
    discovery_warning: Optional[str] = None
    fallback_engine_id: Optional[str] = None
    engine_id: Optional[str] = None
    model: Optional[str] = None
    pipeline: Optional[bool] = None

# =============================================================================
# Protocol Models
# =============================================================================

class ProtocolCreateBase(BaseModel):
    protocol_name: str = Field(..., min_length=1, description="Name of the protocol run")
    description: Optional[str] = None
    base_branch: str = "main"
    template_source: Optional[Any] = None
    template_config: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        if "protocol_name" not in normalized and "name" in normalized:
            normalized["protocol_name"] = normalized.pop("name")
        if "base_branch" not in normalized and "branch_name" in normalized:
            normalized["base_branch"] = normalized.pop("branch_name")
        if "template_source" not in normalized and "template" in normalized:
            normalized["template_source"] = normalized.pop("template")
        if "template_config" not in normalized and "inputs" in normalized:
            normalized["template_config"] = normalized.pop("inputs")
        return normalized


class ProtocolCreate(ProtocolCreateBase):
    project_id: int

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
    protocol_root: Optional[str] = None
    description: Optional[str] = None
    template_config: Optional[Dict[str, Any]] = None
    template_source: Optional[Any] = None
    summary: Optional[str] = None
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_effective_hash: Optional[str] = None
    policy_effective_json: Optional[Dict[str, Any]] = None
    windmill_flow_id: Optional[str]
    speckit_metadata: Optional[Dict[str, Any]]
    linked_sprint_id: Optional[int] = None
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
    status: str = "configured"
    default_model: Optional[str] = None
    command_dir: Optional[str] = None
    enabled: Optional[bool] = None
    command: Optional[str] = None
    endpoint: Optional[str] = None
    sandbox: Optional[str] = None
    format: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None

class AgentConfigUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    enabled: Optional[bool] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    capabilities: Optional[List[str]] = None
    command_dir: Optional[str] = None
    command: Optional[str] = None
    endpoint: Optional[str] = None
    sandbox: Optional[str] = None
    format: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None

class AgentDefaults(BaseModel):
    model_config = ConfigDict(extra="allow")
    code_gen: Optional[str] = None
    planning: Optional[str] = None
    exec: Optional[str] = None
    qa: Optional[str] = None
    discovery: Optional[str] = None
    prompts: Optional[Dict[str, str]] = None

class AgentPromptTemplate(BaseModel):
    id: str
    name: str
    path: str
    kind: Optional[str] = None
    engine_id: Optional[str] = None
    model: Optional[str] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None
    source: Optional[str] = None

class AgentPromptUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    kind: Optional[str] = None
    engine_id: Optional[str] = None
    model: Optional[str] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None

class AgentProjectOverrides(BaseModel):
    model_config = ConfigDict(extra="allow")
    inherit: Optional[bool] = None
    agents: Optional[Dict[str, Dict[str, Any]]] = None
    defaults: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Dict[str, Any]]] = None
    assignments: Optional[Dict[str, Any]] = None

class AgentProcessAssignment(BaseModel):
    agent_id: Optional[str] = None
    prompt_id: Optional[str] = None
    model_override: Optional[str] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class AgentAssignments(BaseModel):
    assignments: Dict[str, AgentProcessAssignment] = Field(default_factory=dict)
    inherit_global: Optional[bool] = None

class AgentOverrides(BaseModel):
    agents: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

class AgentHealthOut(BaseModel):
    agent_id: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class AgentTestCheckOut(BaseModel):
    name: str
    ok: bool
    error: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AgentTestRequest(BaseModel):
    # Optional overrides from the UI modal; these are not persisted.
    overrides: Optional[AgentConfigUpdate] = None


class AgentTestOut(BaseModel):
    agent_id: str
    ok: bool
    checks: List[AgentTestCheckOut] = Field(default_factory=list)
    duration_ms: Optional[float] = None

class AgentMetricsOut(BaseModel):
    agent_id: str
    active_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    total_steps: int = 0
    last_activity_at: Optional[Any] = None

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
    protocol_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    spec_run_id: Optional[int] = None
    event_type: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    event_category: Optional[str] = None
    created_at: Any
    protocol_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None

# =============================================================================
# Application Logs
# =============================================================================

class AppLogEntry(BaseModel):
    id: int
    timestamp: str
    level: str
    source: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class AppLogsResponse(BaseModel):
    logs: List[AppLogEntry]

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


class WorkItemArtifactRefsOut(BaseModel):
    task_dir: str
    context_pack_json: str
    context_pack_md: str
    review_report_json: str
    review_report_md: str
    test_report_json: str
    test_report_md: str
    rework_pack_json: str
    step_artifacts_dir: str


class WorkItemOut(BaseModel):
    id: int
    project_id: int
    protocol_run_id: int
    title: str
    status: str
    context_status: str
    review_status: str
    qa_status: str
    owner_agent: Optional[str] = None
    helper_agents: List[str] = Field(default_factory=list)
    task_dir: Optional[str] = None
    artifact_refs: WorkItemArtifactRefsOut
    depends_on: List[int] = Field(default_factory=list)
    pr_ready: bool = False
    blocking_clarifications: int = 0
    blocking_policy_findings: int = 0
    iteration_count: int = 0
    max_iterations: int = 0
    summary: Optional[str] = None


class BuildContextRequest(BaseModel):
    refresh: bool = False


class WorkItemImplementRequest(BaseModel):
    owner_agent: Optional[str] = None


class WorkItemReviewOut(BaseModel):
    verdict: str
    summary: str
    blocking_findings: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class WorkItemQAOut(BaseModel):
    work_item: WorkItemOut
    qa: QAResultOut


class BrownfieldRunRequest(BaseModel):
    feature_request: str
    feature_name: Optional[str] = None
    output_mode: str = "task_cycle"
    branch: Optional[str] = None
    protocol_name: Optional[str] = None
    overwrite_protocol: bool = False
    owner_agent: Optional[str] = None
    helper_agents: List[str] = Field(default_factory=list)
    allow_helper_agents: bool = False


class BrownfieldRunOut(BaseModel):
    success: bool
    project_id: int
    output_mode: str
    spec_run_id: Optional[int] = None
    spec_path: Optional[str] = None
    plan_path: Optional[str] = None
    tasks_path: Optional[str] = None
    protocol: Optional[ProtocolOut] = None
    work_items: List[WorkItemOut] = Field(default_factory=list)
    next_work_item_id: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)


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
    spec_run_id: Optional[int] = None
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    task_board_status: Optional[str] = None
    sprint_id: Optional[int] = None
    sprint_name: Optional[str] = None
    sprint_status: Optional[str] = None
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

class CommitOut(BaseModel):
    sha: str
    message: str
    author: str
    date: str

class PullRequestOut(BaseModel):
    id: str
    title: str
    branch: str
    status: str  # open, merged, closed
    checks: str  # passing, failing, pending, unknown
    url: str
    author: str
    created_at: str

class WorktreeOut(BaseModel):
    """Worktree info with associated protocol/spec run details."""
    branch_name: str
    worktree_path: Optional[str] = None
    protocol_run_id: Optional[int] = None
    protocol_name: Optional[str] = None
    protocol_status: Optional[str] = None
    spec_run_id: Optional[int] = None
    last_commit_sha: Optional[str] = None
    last_commit_message: Optional[str] = None
    last_commit_date: Optional[str] = None
    pr_url: Optional[str] = None


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

class SyncProtocolToSprintRequest(BaseModel):
    sprint_id: int

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
