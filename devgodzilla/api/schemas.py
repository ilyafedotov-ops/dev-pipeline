from typing import Any, Dict, List, Optional
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
    config: Optional[Dict[str, Any]] = None

class ProjectOut(APIModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    git_url: Optional[str]
    local_path: Optional[str]
    created_at: Any
    updated_at: Any
    constitution_version: Optional[str] = None

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
    summary: Optional[str]
    windmill_flow_id: Optional[str]
    speckit_metadata: Optional[Dict[str, Any]]
    created_at: Any
    updated_at: Any

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
    assigned_agent: Optional[str]
    depends_on: Optional[List[str]] = None
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

# =============================================================================
# Clarification Models
# =============================================================================

class ClarificationAnswer(BaseModel):
    answer: str
    answered_by: Optional[str] = None

class ClarificationOut(APIModel):
    id: int
    protocol_run_id: Optional[int]
    question: str
    status: str
    answer: Optional[Dict[str, Any]]
    created_at: Any
    answered_at: Optional[Any]
