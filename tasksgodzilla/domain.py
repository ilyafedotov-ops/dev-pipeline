from dataclasses import dataclass
from typing import Optional


class ProtocolStatus:
    PENDING = "pending"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_QA = "needs_qa"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class Project:
    id: int
    name: str
    git_url: str
    local_path: Optional[str]
    base_branch: str
    ci_provider: Optional[str]
    secrets: Optional[dict]
    default_models: Optional[dict]
    created_at: str
    updated_at: str


@dataclass
class ProtocolRun:
    id: int
    project_id: int
    protocol_name: str
    status: str
    base_branch: str
    worktree_path: Optional[str]
    protocol_root: Optional[str]
    description: Optional[str]
    template_config: Optional[dict]
    template_source: Optional[dict]
    created_at: str
    updated_at: str


@dataclass
class StepRun:
    id: int
    protocol_run_id: int
    step_index: int
    step_name: str
    step_type: str
    status: str
    retries: int
    model: Optional[str]
    engine_id: Optional[str]
    policy: Optional[object]
    runtime_state: Optional[dict]
    summary: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class Event:
    id: int
    protocol_run_id: int
    step_run_id: Optional[int]
    event_type: str
    message: str
    metadata: Optional[dict]
    created_at: str
    protocol_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
