"""
DevGodzilla Domain Models

Data classes representing the core entities in the DevGodzilla system.
These are used for data transfer between storage and services.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# Status Constants

class ProtocolStatus:
    """Protocol run status values."""
    PENDING = "pending"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    NEEDS_QA = "needs_qa"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class StepStatus:
    """Step run status values."""
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_QA = "needs_qa"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class JobRunStatus:
    """Windmill job run status values."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Core Domain Models

@dataclass
class Project:
    """A project represents a codebase being managed by DevGodzilla."""
    id: int
    name: str
    git_url: str
    base_branch: str
    created_at: str
    updated_at: str
    local_path: Optional[str] = None
    ci_provider: Optional[str] = None
    secrets: Optional[Dict[str, Any]] = None
    default_models: Optional[Dict[str, str]] = None
    # Policy configuration
    project_classification: Optional[str] = None
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_overrides: Optional[Dict[str, Any]] = None
    policy_repo_local_enabled: Optional[bool] = None
    policy_effective_hash: Optional[str] = None
    policy_enforcement_mode: Optional[str] = None
    # Constitution tracking (new for DevGodzilla)
    constitution_version: Optional[str] = None
    constitution_hash: Optional[str] = None


@dataclass
class ProtocolRun:
    """
    A protocol run represents a single execution of a development protocol.
    
    Extended with Windmill integration fields for DAG execution.
    """
    id: int
    project_id: int
    protocol_name: str
    status: str
    base_branch: str
    created_at: str
    updated_at: str
    worktree_path: Optional[str] = None
    protocol_root: Optional[str] = None
    description: Optional[str] = None
    template_config: Optional[Dict[str, Any]] = None
    template_source: Optional[Dict[str, Any]] = None
    # Policy audit
    policy_pack_key: Optional[str] = None
    policy_pack_version: Optional[str] = None
    policy_effective_hash: Optional[str] = None
    policy_effective_json: Optional[Dict[str, Any]] = None
    # Windmill integration (new for DevGodzilla)
    windmill_flow_id: Optional[str] = None
    speckit_metadata: Optional[Dict[str, Any]] = None


@dataclass
class StepRun:
    """
    A step represents a single task within a protocol run.
    
    Extended with DAG support for Windmill execution.
    """
    id: int
    protocol_run_id: int
    step_index: int
    step_name: str
    step_type: str
    status: str
    created_at: str
    updated_at: str
    retries: int = 0
    model: Optional[str] = None
    engine_id: Optional[str] = None
    policy: Optional[Dict[str, Any]] = None
    runtime_state: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    # DAG support (new for DevGodzilla)
    depends_on: List[int] = field(default_factory=list)
    parallel_group: Optional[str] = None
    # Agent assignment (new for DevGodzilla)
    assigned_agent: Optional[str] = None


@dataclass
class Event:
    """An event represents a significant occurrence during protocol execution."""
    id: int
    protocol_run_id: int
    event_type: str
    message: str
    created_at: str
    step_run_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    # Enrichment fields (populated by queries)
    protocol_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None


@dataclass
class JobRun:
    """
    A job run represents a single Windmill job execution.
    
    Renamed from CodexRun to be more generic for multi-agent support.
    """
    run_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    run_kind: Optional[str] = None
    project_id: Optional[int] = None
    protocol_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    queue: Optional[str] = None
    attempt: Optional[int] = None
    worker_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    prompt_version: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    log_path: Optional[str] = None
    cost_tokens: Optional[int] = None
    cost_cents: Optional[int] = None
    # Windmill integration
    windmill_job_id: Optional[str] = None


# Alias for backward compatibility
CodexRun = JobRun


@dataclass
class RunArtifact:
    """An artifact produced by a job run (logs, outputs, diffs)."""
    id: int
    run_id: str
    name: str
    kind: str
    path: str
    created_at: str
    sha256: Optional[str] = None
    bytes: Optional[int] = None


@dataclass
class PolicyPack:
    """A policy pack defines governance rules for projects."""
    id: int
    key: str
    version: str
    name: str
    status: str
    pack: Dict[str, Any]
    created_at: str
    updated_at: str
    description: Optional[str] = None


@dataclass
class Clarification:
    """A clarification request for ambiguous requirements."""
    id: int
    scope: str
    project_id: int
    key: str
    question: str
    status: str
    created_at: str
    updated_at: str
    protocol_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    recommended: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = None
    applies_to: Optional[str] = None
    blocking: bool = False
    answer: Optional[Dict[str, Any]] = None
    answered_at: Optional[str] = None
    answered_by: Optional[str] = None


# New models for DevGodzilla

@dataclass
class FeedbackEvent:
    """
    Tracks QA feedback loop events for observability.
    
    Records when errors occur and what actions are taken (clarify, re-plan, retry).
    """
    id: int
    protocol_run_id: int
    error_type: str
    action_taken: str
    attempt_number: int
    created_at: str
    step_run_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class Constitution:
    """
    Constitution file metadata for a project.
    
    Tracks the governance principles that guide all development.
    """
    id: int
    project_id: int
    version: str
    content_hash: str
    created_at: str
    updated_at: str
    file_path: Optional[str] = None
    articles: Optional[List[Dict[str, Any]]] = None


@dataclass
class SpecKitSpec:
    """
    SpecKit specification tracking.
    
    Links to the spec files (feature-spec.md, plan.md, tasks.md).
    """
    id: int
    protocol_run_id: int
    spec_type: str  # 'feature', 'plan', 'tasks'
    file_path: str
    content_hash: str
    created_at: str
    updated_at: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentConfig:
    """
    Agent configuration for a specific engine.
    
    Maps to the agents.yaml configuration structure.
    """
    id: str  # e.g., 'codex', 'opencode', 'claude-code'
    name: str
    kind: str  # 'cli', 'ide', 'api'
    enabled: bool = True
    default_model: Optional[str] = None
    sandbox: Optional[str] = None
    command_dir: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
