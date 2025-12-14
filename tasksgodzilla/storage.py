import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol

from tasksgodzilla.logging import get_logger

try:  # Optional Postgres support
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - Postgres optional
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore
    ConnectionPool = None  # type: ignore

from .domain import Clarification, CodexRun, Event, PolicyPack, Project, ProtocolRun, RunArtifact, StepRun


DEFAULT_POLICY_PACK_KEY = "default"
DEFAULT_POLICY_PACK_VERSION = "1.0"
DEFAULT_POLICY_PACK: dict[str, Any] = {
    "meta": {
        "key": DEFAULT_POLICY_PACK_KEY,
        "name": "Default",
        "version": DEFAULT_POLICY_PACK_VERSION,
        "description": "Baseline policy pack (warnings by default).",
    },
    "defaults": {},
    "requirements": {},
    "clarifications": [],
    "enforcement": {
        "mode": "warn",
        # When a project sets policy_enforcement_mode=block, these finding codes become blocking.
        # Keep this list conservative; packs can override as needed.
        "block_codes": [
            "policy.ci.required_check_missing",
            "policy.ci.required_check_not_executable",
            "policy.protocol.missing_file",
            "policy.step.missing_section",
            "policy.step.file_missing",
        ],
    },
}

BEGINNER_GUIDED_POLICY_PACK_KEY = "beginner-guided"
BEGINNER_GUIDED_POLICY_PACK_VERSION = "1.0"
BEGINNER_GUIDED_POLICY_PACK: dict[str, Any] = {
    "meta": {
        "key": BEGINNER_GUIDED_POLICY_PACK_KEY,
        "name": "Beginner Guided",
        "version": BEGINNER_GUIDED_POLICY_PACK_VERSION,
        "description": "More structure and safety for inexperienced users (warnings by default).",
    },
    "defaults": {
        "qa": {"policy": "light"},
        "ci": {
            "required_checks": [
                "scripts/ci/test.sh",
                "scripts/ci/lint.sh",
                "scripts/ci/typecheck.sh",
                "scripts/ci/build.sh",
            ]
        },
    },
    "requirements": {
        "step_sections": ["Sub-tasks", "Verification", "Rollback", "Definition of Done"],
        "protocol_files": ["plan.md", "context.md", "log.md"],
    },
    "clarifications": [],
    "enforcement": {
        "mode": "warn",
        "block_codes": [
            "policy.ci.required_check_missing",
            "policy.ci.required_check_not_executable",
            "policy.protocol.missing_file",
            "policy.step.missing_section",
            "policy.step.file_missing",
        ],
    },
}

STARTUP_FAST_POLICY_PACK_KEY = "startup-fast"
STARTUP_FAST_POLICY_PACK_VERSION = "1.0"
STARTUP_FAST_POLICY_PACK: dict[str, Any] = {
    "meta": {
        "key": STARTUP_FAST_POLICY_PACK_KEY,
        "name": "Startup Fast",
        "version": STARTUP_FAST_POLICY_PACK_VERSION,
        "description": "Minimal process overhead; focus on iteration speed (warnings by default).",
    },
    "defaults": {
        "qa": {"policy": "full"},
    },
    "requirements": {},
    "clarifications": [],
    "enforcement": {
        "mode": "warn",
        # Startup-fast keeps strict-mode scope narrow by default.
        "block_codes": [
            "policy.ci.required_check_missing",
            "policy.ci.required_check_not_executable",
        ],
    },
}

TEAM_STANDARD_POLICY_PACK_KEY = "team-standard"
TEAM_STANDARD_POLICY_PACK_VERSION = "1.0"
TEAM_STANDARD_POLICY_PACK: dict[str, Any] = {
    "meta": {
        "key": TEAM_STANDARD_POLICY_PACK_KEY,
        "name": "Team Standard",
        "version": TEAM_STANDARD_POLICY_PACK_VERSION,
        "description": "Balanced defaults for most professional teams (warnings by default).",
    },
    "defaults": {
        "models": {
            "planning": "gpt-5.1-high",
            "decompose": "gpt-5.1-high",
            "exec": "gpt-5.1-codex-max",
            "qa": "gpt-5.1-codex-max",
        },
        "qa": {"policy": "full", "auto_after_exec": False, "auto_on_ci": True},
        "ci": {
            "required_checks": [
                "scripts/ci/test.sh",
                "scripts/ci/lint.sh",
                "scripts/ci/typecheck.sh",
                "scripts/ci/build.sh",
            ]
        },
        "git": {"draft_pr_default": True, "branch_pattern": "<number>-<task>"},
    },
    "requirements": {
        "step_sections": [
            "Context",
            "Scope",
            "Sub-tasks",
            "Verification",
            "Rollback",
            "Observability",
            "Definition of Done",
        ],
        "protocol_files": ["plan.md", "context.md", "log.md"],
    },
    "clarifications": [
        {
            "key": "review_policy",
            "question": "How many approvals are required before merge?",
            "options": ["1-approval", "2-approvals"],
            "recommended": "1-approval",
            "blocking": False,
            "applies_to": "execution",
        }
    ],
    "enforcement": {
        "mode": "warn",
        "block_codes": [
            "policy.ci.required_check_missing",
            "policy.ci.required_check_not_executable",
            "policy.protocol.missing_file",
            "policy.step.missing_section",
            "policy.step.file_missing",
        ],
    },
}

ENTERPRISE_COMPLIANCE_POLICY_PACK_KEY = "enterprise-compliance"
ENTERPRISE_COMPLIANCE_POLICY_PACK_VERSION = "1.0"
ENTERPRISE_COMPLIANCE_POLICY_PACK: dict[str, Any] = {
    "meta": {
        "key": ENTERPRISE_COMPLIANCE_POLICY_PACK_KEY,
        "name": "Enterprise Compliance",
        "version": ENTERPRISE_COMPLIANCE_POLICY_PACK_VERSION,
        "description": "Regulated/audited workflows; designed for policy_enforcement_mode=block.",
    },
    "defaults": {
        "models": {
            "planning": "gpt-5.1-high",
            "decompose": "gpt-5.1-high",
            "exec": "gpt-5.1-codex-max",
            "qa": "gpt-5.1-codex-max",
        },
        "qa": {"policy": "full", "auto_after_exec": False, "auto_on_ci": True},
        "ci": {
            "required_checks": [
                "scripts/ci/test.sh",
                "scripts/ci/lint.sh",
                "scripts/ci/typecheck.sh",
                "scripts/ci/build.sh",
                "scripts/ci/security.sh",
            ]
        },
        "git": {"draft_pr_default": False, "branch_pattern": "<number>-<task>"},
    },
    "requirements": {
        "step_sections": [
            "Context",
            "Risk Assessment",
            "Security Considerations",
            "Sub-tasks",
            "Verification",
            "Rollback",
            "Audit Notes",
            "Definition of Done",
        ],
        "protocol_files": ["plan.md", "context.md", "log.md"],
    },
    "clarifications": [
        {
            "key": "data_classification",
            "question": "What data classification applies to this project?",
            "options": ["public", "internal", "confidential", "regulated"],
            "recommended": "internal",
            "blocking": True,
            "applies_to": "onboarding",
        }
    ],
    "enforcement": {
        "mode": "warn",
        "block_codes": [
            "policy.ci.required_check_missing",
            "policy.ci.required_check_not_executable",
            "policy.protocol.missing_file",
            "policy.step.missing_section",
            "policy.step.file_missing",
        ],
    },
}

_KNOWN_PROJECT_CLASSIFICATIONS: dict[str, tuple[str, str]] = {
    "default": (DEFAULT_POLICY_PACK_KEY, DEFAULT_POLICY_PACK_VERSION),
    "beginner-guided": (BEGINNER_GUIDED_POLICY_PACK_KEY, BEGINNER_GUIDED_POLICY_PACK_VERSION),
    "startup-fast": (STARTUP_FAST_POLICY_PACK_KEY, STARTUP_FAST_POLICY_PACK_VERSION),
    "team-standard": (TEAM_STANDARD_POLICY_PACK_KEY, TEAM_STANDARD_POLICY_PACK_VERSION),
    "enterprise-compliance": (ENTERPRISE_COMPLIANCE_POLICY_PACK_KEY, ENTERPRISE_COMPLIANCE_POLICY_PACK_VERSION),
}


def _normalize_project_classification(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized if normalized in _KNOWN_PROJECT_CLASSIFICATIONS else None


def _resolve_policy_selection(
    *,
    project_classification: Optional[str],
    policy_pack_key: Optional[str],
    policy_pack_version: Optional[str],
) -> tuple[Optional[str], str, str]:
    """
    Resolve the effective policy pack selection for a new project.
    Returns (normalized_classification, effective_pack_key, effective_pack_version).
    """
    if policy_pack_key:
        return (
            _normalize_project_classification(project_classification),
            policy_pack_key,
            policy_pack_version or DEFAULT_POLICY_PACK_VERSION,
        )
    normalized = _normalize_project_classification(project_classification)
    if normalized:
        key, version = _KNOWN_PROJECT_CLASSIFICATIONS[normalized]
        return normalized, key, policy_pack_version or version
    return None, DEFAULT_POLICY_PACK_KEY, policy_pack_version or DEFAULT_POLICY_PACK_VERSION

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    local_path TEXT,
    ci_provider TEXT,
    project_classification TEXT,
    secrets TEXT,
    default_models TEXT,
    policy_pack_key TEXT,
    policy_pack_version TEXT,
    policy_overrides TEXT,
    policy_repo_local_enabled INTEGER,
    policy_effective_hash TEXT,
    policy_enforcement_mode TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    pack TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, version)
);

CREATE TABLE IF NOT EXISTS protocol_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    worktree_path TEXT,
    protocol_root TEXT,
    description TEXT,
    template_config TEXT,
    template_source TEXT,
    policy_pack_key TEXT,
    policy_pack_version TEXT,
    policy_effective_hash TEXT,
    policy_effective_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    retries INTEGER DEFAULT 0,
    model TEXT,
    engine_id TEXT,
    policy TEXT,
    runtime_state TEXT,
    summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS codex_runs (
    run_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    run_kind TEXT,
    project_id INTEGER,
    protocol_run_id INTEGER,
    step_run_id INTEGER,
    queue TEXT,
    attempt INTEGER,
    worker_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    finished_at DATETIME,
    prompt_version TEXT,
    params TEXT,
    result TEXT,
    error TEXT,
    log_path TEXT,
    cost_tokens INTEGER,
    cost_cents INTEGER
);

CREATE INDEX IF NOT EXISTS idx_codex_runs_job_status ON codex_runs(job_type, status, created_at);

CREATE TABLE IF NOT EXISTS run_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    bytes INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, name)
);
CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_id ON run_artifacts(run_id, created_at);

CREATE TABLE IF NOT EXISTS clarifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    key TEXT NOT NULL,
    question TEXT NOT NULL,
    recommended TEXT,
    options TEXT,
    applies_to TEXT,
    blocking INTEGER DEFAULT 0,
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    answered_at DATETIME,
    answered_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scope, key)
);
CREATE INDEX IF NOT EXISTS idx_clarifications_project ON clarifications(project_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_clarifications_protocol ON clarifications(protocol_run_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_clarifications_step ON clarifications(step_run_id, status, created_at);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    local_path TEXT,
    base_branch TEXT NOT NULL,
    ci_provider TEXT,
    project_classification TEXT,
    secrets JSONB,
    default_models JSONB,
    policy_pack_key TEXT,
    policy_pack_version TEXT,
    policy_overrides JSONB,
    policy_repo_local_enabled BOOLEAN,
    policy_effective_hash TEXT,
    policy_enforcement_mode TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_packs (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    pack JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, version)
);

CREATE TABLE IF NOT EXISTS protocol_runs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    worktree_path TEXT,
    protocol_root TEXT,
    description TEXT,
    template_config JSONB,
    template_source JSONB,
    policy_pack_key TEXT,
    policy_pack_version TEXT,
    policy_effective_hash TEXT,
    policy_effective_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS step_runs (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    retries INTEGER DEFAULT 0,
    model TEXT,
    engine_id TEXT,
    policy JSONB,
    runtime_state JSONB,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS codex_runs (
    run_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    run_kind TEXT,
    project_id INTEGER,
    protocol_run_id INTEGER,
    step_run_id INTEGER,
    queue TEXT,
    attempt INTEGER,
    worker_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    prompt_version TEXT,
    params JSONB,
    result JSONB,
    error TEXT,
    log_path TEXT,
    cost_tokens INTEGER,
    cost_cents INTEGER
);

CREATE INDEX IF NOT EXISTS idx_codex_runs_job_status ON codex_runs(job_type, status, created_at);

CREATE TABLE IF NOT EXISTS run_artifacts (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, name)
);
CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_id ON run_artifacts(run_id, created_at);

CREATE TABLE IF NOT EXISTS clarifications (
    id SERIAL PRIMARY KEY,
    scope TEXT NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    key TEXT NOT NULL,
    question TEXT NOT NULL,
    recommended JSONB,
    options JSONB,
    applies_to TEXT,
    blocking BOOLEAN DEFAULT false,
    answer JSONB,
    status TEXT NOT NULL DEFAULT 'open',
    answered_at TIMESTAMP,
    answered_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scope, key)
);
CREATE INDEX IF NOT EXISTS idx_clarifications_project ON clarifications(project_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_clarifications_protocol ON clarifications(protocol_run_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_clarifications_step ON clarifications(step_run_id, status, created_at);
"""

_UNSET = object()


class BaseDatabase(Protocol):
    def init_schema(self) -> None: ...
    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str],
        default_models: Optional[dict],
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project: ...
    def update_project_local_path(self, project_id: int, local_path: str) -> Project: ...
    def update_project_policy(
        self,
        project_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        policy_overrides: Optional[dict] = None,
        policy_repo_local_enabled: Optional[bool] = None,
        policy_effective_hash: Optional[str] = None,
        policy_enforcement_mode: Optional[str] = None,
    ) -> Project: ...
    def get_project(self, project_id: int) -> Project: ...
    def list_projects(self) -> List[Project]: ...
    def create_protocol_run(self, project_id: int, protocol_name: str, status: str, base_branch: str, worktree_path: Optional[str], protocol_root: Optional[str], description: Optional[str], template_config: Optional[dict] = None, template_source: Optional[dict] = None) -> ProtocolRun: ...
    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun: ...
    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun: ...
    def update_protocol_policy_audit(
        self,
        run_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        policy_effective_hash: Optional[str] = None,
        policy_effective_json: Optional[dict] = None,
    ) -> ProtocolRun: ...
    def get_protocol_run(self, run_id: int) -> ProtocolRun: ...
    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]: ...
    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]: ...
    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]: ...
    def list_all_protocol_runs(self) -> List[ProtocolRun]: ...
    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun: ...
    def create_step_run(self, protocol_run_id: int, step_index: int, step_name: str, step_type: str, status: str, model: Optional[str] = None, engine_id: Optional[str] = None, retries: int = 0, summary: Optional[str] = None, policy: Optional[dict] = None) -> StepRun: ...
    def get_step_run(self, step_run_id: int) -> StepRun: ...
    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]: ...
    def list_all_step_runs(self) -> List[StepRun]: ...
    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]: ...
    def update_step_status(self, step_run_id: int, status: str, retries: Optional[int] = None, summary: Optional[str] = None, model: Optional[str] = None, engine_id: Optional[str] = None, runtime_state: Optional[dict] = None, expected_status: Optional[str] = None) -> StepRun: ...
    def append_event(self, protocol_run_id: int, event_type: str, message: str, metadata: Optional[Dict[str, Any]] = None, step_run_id: Optional[int] = None, request_id: Optional[str] = None, job_id: Optional[str] = None) -> Event: ...
    def list_events(self, protocol_run_id: int) -> List[Event]: ...
    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]: ...
    def create_codex_run(
        self,
        run_id: str,
        job_type: str,
        status: str,
        *,
        run_kind: Optional[str] = None,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        queue: Optional[str] = None,
        attempt: Optional[int] = None,
        worker_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        params: Optional[dict] = None,
        log_path: Optional[str] = None,
        started_at: Optional[str] = None,
        cost_tokens: Optional[int] = None,
        cost_cents: Optional[int] = None,
    ) -> CodexRun: ...
    def update_codex_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        run_kind: Any = _UNSET,
        project_id: Any = _UNSET,
        protocol_run_id: Any = _UNSET,
        step_run_id: Any = _UNSET,
        queue: Any = _UNSET,
        attempt: Any = _UNSET,
        worker_id: Any = _UNSET,
        prompt_version: Any = _UNSET,
        params: Any = _UNSET,
        result: Any = _UNSET,
        error: Any = _UNSET,
        log_path: Any = _UNSET,
        cost_tokens: Any = _UNSET,
        cost_cents: Any = _UNSET,
        started_at: Any = _UNSET,
        finished_at: Any = _UNSET,
    ) -> CodexRun: ...
    def get_codex_run(self, run_id: str) -> CodexRun: ...
    def list_codex_runs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        run_kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[CodexRun]: ...

    def upsert_run_artifact(
        self,
        run_id: str,
        name: str,
        *,
        kind: str,
        path: str,
        sha256: Optional[str] = None,
        bytes: Optional[int] = None,
    ) -> RunArtifact: ...

    def list_run_artifacts(self, run_id: str, *, kind: Optional[str] = None, limit: int = 100) -> List[RunArtifact]: ...
    def get_run_artifact(self, artifact_id: int) -> RunArtifact: ...

    def upsert_policy_pack(
        self,
        *,
        key: str,
        version: str,
        name: str,
        description: Optional[str],
        status: str,
        pack: dict,
    ) -> PolicyPack: ...

    def list_policy_packs(self, *, key: Optional[str] = None, status: Optional[str] = None) -> List[PolicyPack]: ...

    def get_policy_pack(self, *, key: str, version: Optional[str] = None) -> PolicyPack: ...

    def upsert_clarification(
        self,
        *,
        scope: str,
        project_id: int,
        key: str,
        question: str,
        recommended: Optional[dict] = None,
        options: Optional[list] = None,
        applies_to: Optional[str] = None,
        blocking: bool = False,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
    ) -> Clarification: ...

    def list_clarifications(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        status: Optional[str] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]: ...

    def answer_clarification(
        self,
        *,
        scope: str,
        key: str,
        answer: Optional[dict],
        answered_by: Optional[str] = None,
        status: str = "answered",
    ) -> Clarification: ...


class Database:
    """
    Lightweight SQLite-backed persistence for orchestrator state.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQLITE)
            # Backward-compatible migration: add local_path column if missing
            cur = conn.execute("PRAGMA table_info(projects)")
            cols = [r[1] for r in cur.fetchall()]
            if "local_path" not in cols:
                conn.execute("ALTER TABLE projects ADD COLUMN local_path TEXT")
            # Backward-compatible migration: policy columns on projects
            project_migrations: list[tuple[str, str]] = [
                ("project_classification", "TEXT"),
                ("policy_pack_key", "TEXT"),
                ("policy_pack_version", "TEXT"),
                ("policy_overrides", "TEXT"),
                ("policy_repo_local_enabled", "INTEGER"),
                ("policy_effective_hash", "TEXT"),
                ("policy_enforcement_mode", "TEXT"),
            ]
            for col_name, col_type in project_migrations:
                if col_name not in cols:
                    conn.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")

            # Backward-compatible migration: policy audit columns on protocol_runs
            cur = conn.execute("PRAGMA table_info(protocol_runs)")
            proto_cols = {r[1] for r in cur.fetchall()}
            protocol_migrations: list[tuple[str, str]] = [
                ("policy_pack_key", "TEXT"),
                ("policy_pack_version", "TEXT"),
                ("policy_effective_hash", "TEXT"),
                ("policy_effective_json", "TEXT"),
            ]
            for col_name, col_type in protocol_migrations:
                if col_name not in proto_cols:
                    conn.execute(f"ALTER TABLE protocol_runs ADD COLUMN {col_name} {col_type}")

            # Backward-compatible migration: add codex_runs linkage columns if missing.
            cur = conn.execute("PRAGMA table_info(codex_runs)")
            codex_cols = {r[1] for r in cur.fetchall()}
            migrations: list[tuple[str, str]] = [
                ("run_kind", "TEXT"),
                ("project_id", "INTEGER"),
                ("protocol_run_id", "INTEGER"),
                ("step_run_id", "INTEGER"),
                ("queue", "TEXT"),
                ("attempt", "INTEGER"),
                ("worker_id", "TEXT"),
            ]
            for col_name, col_type in migrations:
                if col_name not in codex_cols:
                    conn.execute(f"ALTER TABLE codex_runs ADD COLUMN {col_name} {col_type}")

            # Create secondary indexes after migrations so existing DBs don't error.
            conn.execute("CREATE INDEX IF NOT EXISTS idx_codex_runs_project ON codex_runs(project_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_codex_runs_protocol ON codex_runs(protocol_run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_codex_runs_step ON codex_runs(step_run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_id ON run_artifacts(run_id, created_at)")

            # Seed a baseline policy pack.
            self._ensure_default_policy_pack_sqlite(conn)

            # Backfill existing projects to a default policy selection (rollout safety).
            try:
                conn.execute(
                    """
                    UPDATE projects
                    SET policy_pack_key = COALESCE(policy_pack_key, ?),
                        policy_pack_version = COALESCE(policy_pack_version, ?),
                        policy_repo_local_enabled = COALESCE(policy_repo_local_enabled, 0),
                        policy_enforcement_mode = COALESCE(policy_enforcement_mode, 'warn')
                    """,
                    (DEFAULT_POLICY_PACK_KEY, DEFAULT_POLICY_PACK_VERSION),
                )
            except Exception:
                pass
            conn.commit()

    def _fetchone(self, query: str, params: Iterable[Any]) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
        return row

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()
        return rows

    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str],
        default_models: Optional[dict],
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project:
        normalized_classification, effective_pack_key, effective_pack_version = _resolve_policy_selection(
            project_classification=project_classification,
            policy_pack_key=policy_pack_key,
            policy_pack_version=policy_pack_version,
        )
        default_models_json = json.dumps(default_models) if default_models else None
        secrets_json = json.dumps(secrets) if secrets else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects (
                    name,
                    git_url,
                    base_branch,
                    ci_provider,
                    project_classification,
                    default_models,
                    secrets,
                    local_path,
                    policy_pack_key,
                    policy_pack_version,
                    policy_overrides,
                    policy_repo_local_enabled,
                    policy_effective_hash,
                    policy_enforcement_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    git_url,
                    base_branch,
                    ci_provider,
                    normalized_classification,
                    default_models_json,
                    secrets_json,
                    local_path,
                    effective_pack_key,
                    effective_pack_version,
                    None,
                    0,
                    None,
                    "warn",
                ),
            )
            project_id = cur.lastrowid
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return self._row_to_project(row)

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET local_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (local_path, project_id),
            )
            conn.commit()
        return self.get_project(project_id)

    def update_project_policy(
        self,
        project_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        clear_policy_pack_version: bool = False,
        policy_overrides: Optional[dict] = None,
        policy_repo_local_enabled: Optional[bool] = None,
        policy_effective_hash: Optional[str] = None,
        policy_enforcement_mode: Optional[str] = None,
    ) -> Project:
        updates: list[str] = []
        params: list[Any] = []
        if policy_pack_key is not None:
            updates.append("policy_pack_key = ?")
            params.append(policy_pack_key)
        if clear_policy_pack_version:
            updates.append("policy_pack_version = ?")
            params.append(None)
        elif policy_pack_version is not None:
            updates.append("policy_pack_version = ?")
            params.append(policy_pack_version)
        if policy_overrides is not None:
            updates.append("policy_overrides = ?")
            params.append(json.dumps(policy_overrides))
        if policy_repo_local_enabled is not None:
            updates.append("policy_repo_local_enabled = ?")
            params.append(1 if policy_repo_local_enabled else 0)
        if policy_effective_hash is not None:
            updates.append("policy_effective_hash = ?")
            params.append(policy_effective_hash)
        if policy_enforcement_mode is not None:
            updates.append("policy_enforcement_mode = ?")
            params.append(policy_enforcement_mode)
        if not updates:
            return self.get_project(project_id)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(project_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()
        return self.get_project(project_id)

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [self._row_to_project(row) for row in rows]

    def upsert_clarification(
        self,
        *,
        scope: str,
        project_id: int,
        key: str,
        question: str,
        recommended: Optional[dict] = None,
        options: Optional[list] = None,
        applies_to: Optional[str] = None,
        blocking: bool = False,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
    ) -> Clarification:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clarifications (
                    scope, project_id, protocol_run_id, step_run_id,
                    key, question, recommended, options, applies_to, blocking,
                    status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
                ON CONFLICT(scope, key) DO UPDATE SET
                    project_id=excluded.project_id,
                    protocol_run_id=excluded.protocol_run_id,
                    step_run_id=excluded.step_run_id,
                    question=excluded.question,
                    recommended=excluded.recommended,
                    options=excluded.options,
                    applies_to=excluded.applies_to,
                    blocking=excluded.blocking,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    scope,
                    project_id,
                    protocol_run_id,
                    step_run_id,
                    key,
                    question,
                    json.dumps(recommended) if recommended is not None else None,
                    json.dumps(options) if options is not None else None,
                    applies_to,
                    1 if blocking else 0,
                ),
            )
            conn.commit()
        row = self._fetchone("SELECT * FROM clarifications WHERE scope = ? AND key = ? LIMIT 1", (scope, key))
        if row is None:
            raise KeyError("Clarification not found after upsert")
        return self._row_to_clarification(row)

    def list_clarifications(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        status: Optional[str] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM clarifications"
        where: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if protocol_run_id is not None:
            where.append("protocol_run_id = ?")
            params.append(protocol_run_id)
        if step_run_id is not None:
            where.append("step_run_id = ?")
            params.append(step_run_id)
        if status:
            where.append("status = ?")
            params.append(status)
        if applies_to:
            where.append("applies_to = ?")
            params.append(applies_to)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(query, tuple(params))
        return [self._row_to_clarification(r) for r in rows]

    def answer_clarification(
        self,
        *,
        scope: str,
        key: str,
        answer: Optional[dict],
        answered_by: Optional[str] = None,
        status: str = "answered",
    ) -> Clarification:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE clarifications
                SET answer = ?,
                    status = ?,
                    answered_at = CURRENT_TIMESTAMP,
                    answered_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE scope = ? AND key = ?
                """,
                (json.dumps(answer) if answer is not None else None, status, answered_by, scope, key),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Clarification {scope}:{key} not found")
            conn.commit()
        row = self._fetchone("SELECT * FROM clarifications WHERE scope = ? AND key = ? LIMIT 1", (scope, key))
        if row is None:
            raise KeyError("Clarification not found after answer")
        return self._row_to_clarification(row)

    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str],
        protocol_root: Optional[str],
        description: Optional[str],
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        template_config_json = json.dumps(template_config) if template_config is not None else None
        template_source_json = json.dumps(template_source) if template_source is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO protocol_runs (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description, template_config, template_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    protocol_name,
                    status,
                    base_branch,
                    worktree_path,
                    protocol_root,
                    description,
                    template_config_json,
                    template_source_json,
                ),
            )
            run_id = cur.lastrowid
            conn.commit()
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = ?", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return self._row_to_protocol(row)

    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE protocol_runs
                SET worktree_path = ?, protocol_root = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (worktree_path, protocol_root, run_id),
            )
        conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE protocol_runs
                SET template_config = ?, template_source = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(template_config) if template_config is not None else None,
                    json.dumps(template_source) if template_source is not None else None,
                    run_id,
                ),
            )
            conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_policy_audit(
        self,
        run_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        policy_effective_hash: Optional[str] = None,
        policy_effective_json: Optional[dict] = None,
    ) -> ProtocolRun:
        updates: list[str] = []
        params: list[Any] = []
        if policy_pack_key is not None:
            updates.append("policy_pack_key = ?")
            params.append(policy_pack_key)
        if policy_pack_version is not None:
            updates.append("policy_pack_version = ?")
            params.append(policy_pack_version)
        if policy_effective_hash is not None:
            updates.append("policy_effective_hash = ?")
            params.append(policy_effective_hash)
        if policy_effective_json is not None:
            updates.append("policy_effective_json = ?")
            params.append(json.dumps(policy_effective_json))
        if not updates:
            return self.get_protocol_run(run_id)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(run_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE protocol_runs SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()
        return self.get_protocol_run(run_id)

    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = ?", (protocol_name,))
        return self._row_to_protocol(row) if row else None

    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]:
        """
        Attempt to locate a protocol run based on branch/ref naming (NNNN-<task>).
        """
        ref = branch.replace("refs/heads/", "").replace("refs/tags/", "")
        parts = ref.split("/")
        # Prefer last segment; also try full ref
        candidates = [ref, parts[-1]]
        for cand in candidates:
            row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = ?", (cand,))
            if row:
                return self._row_to_protocol(row)
        return None

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return [self._row_to_protocol(row) for row in rows]

    def list_all_protocol_runs(self) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs ORDER BY created_at DESC",
        )
        return [self._row_to_protocol(row) for row in rows]

    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun:
        with self._connect() as conn:
            if expected_status:
                cur = conn.execute(
                    "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
                    (status, run_id, expected_status),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"ProtocolRun {run_id} status conflict")
            else:
                conn.execute(
                    "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, run_id),
                )
            conn.commit()
        run = self.get_protocol_run(run_id)
        log = get_logger(__name__)
        log.info("protocol_status_updated", extra={"protocol_run_id": run_id, "status": status})
        return run

    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        model: Optional[str],
        engine_id: Optional[str] = None,
        retries: int = 0,
        summary: Optional[str] = None,
        policy: Optional[dict] = None,
    ) -> StepRun:
        policy_json = json.dumps(policy) if policy is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO step_runs (protocol_run_id, step_index, step_name, step_type, status, model, engine_id, policy, runtime_state, summary, retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    protocol_run_id,
                    step_index,
                    step_name,
                    step_type,
                    status,
                    model,
                    engine_id,
                    policy_json,
                    None,
                    summary,
                    retries,
                ),
            )
            step_id = cur.lastrowid
            conn.commit()
        return self.get_step_run(step_id)

    def get_step_run(self, step_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = ?", (step_id,))
        if row is None:
            raise KeyError(f"StepRun {step_id} not found")
        return self._row_to_step(row)

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = ? ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [self._row_to_step(row) for row in rows]

    def list_all_step_runs(self) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs ORDER BY created_at DESC",
        )
        return [self._row_to_step(row) for row in rows]

    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]:
        row = self._fetchone(
            "SELECT * FROM step_runs WHERE protocol_run_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
            (protocol_run_id,),
        )
        return self._row_to_step(row) if row else None

    def update_step_status(
        self,
        step_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
        expected_status: Optional[str] = None,
    ) -> StepRun:
        runtime_state_json = json.dumps(runtime_state) if runtime_state is not None else None
        with self._connect() as conn:
            if expected_status:
                cur = conn.execute(
                    """
                    UPDATE step_runs
                    SET status = ?,
                        summary = COALESCE(?, summary),
                        model = COALESCE(?, model),
                        engine_id = COALESCE(?, engine_id),
                        runtime_state = COALESCE(?, runtime_state),
                        retries = COALESCE(?, retries),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = ?
                    """,
                    (status, summary, model, engine_id, runtime_state_json, retries, step_id, expected_status),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"StepRun {step_id} status conflict")
            else:
                conn.execute(
                    """
                    UPDATE step_runs
                    SET status = ?,
                        summary = COALESCE(?, summary),
                        model = COALESCE(?, model),
                        engine_id = COALESCE(?, engine_id),
                        runtime_state = COALESCE(?, runtime_state),
                        retries = COALESCE(?, retries),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, summary, model, engine_id, runtime_state_json, retries, step_id),
                )
            conn.commit()
        step = self.get_step_run(step_id)
        log = get_logger(__name__)
        log.info(
            "step_status_updated",
            extra={"step_run_id": step_id, "protocol_run_id": step.protocol_run_id, "status": status},
        )
        return step

    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        step_run_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Event:
        meta = dict(metadata or {})
        if request_id and "request_id" not in meta:
            meta["request_id"] = request_id
        if job_id and "job_id" not in meta:
            meta["job_id"] = job_id
        metadata_json = json.dumps(meta) if meta else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (protocol_run_id, step_run_id, event_type, message, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (protocol_run_id, step_run_id, event_type, message, metadata_json),
            )
            event_id = cur.lastrowid
            conn.commit()
        row = self._fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
        return self._row_to_event(row)  # type: ignore[arg-type]

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = ? ORDER BY created_at DESC",
            (protocol_run_id,),
        )
        return [self._row_to_event(row) for row in rows]

    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]:
        """
        Return recent events across projects, newest first. Includes protocol/project context for console views.
        """
        limit = max(1, min(int(limit), 500))
        base = """
        SELECT e.*, pr.protocol_name, pr.project_id, p.name AS project_name
        FROM events e
        JOIN protocol_runs pr ON e.protocol_run_id = pr.id
        JOIN projects p ON pr.project_id = p.id
        """
        params: list[Any] = []
        if project_id is not None:
            base += " WHERE pr.project_id = ?"
            params.append(project_id)
        base += " ORDER BY e.created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [self._row_to_event(row) for row in rows]

    def create_codex_run(
        self,
        run_id: str,
        job_type: str,
        status: str,
        *,
        run_kind: Optional[str] = None,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        queue: Optional[str] = None,
        attempt: Optional[int] = None,
        worker_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        params: Optional[dict] = None,
        log_path: Optional[str] = None,
        started_at: Optional[str] = None,
        cost_tokens: Optional[int] = None,
        cost_cents: Optional[int] = None,
    ) -> CodexRun:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO codex_runs (
                    run_id,
                    job_type,
                    status,
                    run_kind,
                    project_id,
                    protocol_run_id,
                    step_run_id,
                    queue,
                    attempt,
                    worker_id,
                    prompt_version,
                    params,
                    log_path,
                    started_at,
                    cost_tokens,
                    cost_cents
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_type,
                    status,
                    run_kind,
                    project_id,
                    protocol_run_id,
                    step_run_id,
                    queue,
                    attempt,
                    worker_id,
                    prompt_version,
                    json.dumps(params) if params is not None else None,
                    log_path,
                    started_at,
                    cost_tokens,
                    cost_cents,
                ),
            )
            conn.commit()
        return self.get_codex_run(run_id)

    def update_codex_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        run_kind: Any = _UNSET,
        project_id: Any = _UNSET,
        protocol_run_id: Any = _UNSET,
        step_run_id: Any = _UNSET,
        queue: Any = _UNSET,
        attempt: Any = _UNSET,
        worker_id: Any = _UNSET,
        prompt_version: Any = _UNSET,
        params: Any = _UNSET,
        result: Any = _UNSET,
        error: Any = _UNSET,
        log_path: Any = _UNSET,
        cost_tokens: Any = _UNSET,
        cost_cents: Any = _UNSET,
        started_at: Any = _UNSET,
        finished_at: Any = _UNSET,
    ) -> CodexRun:
        updates: list[str] = []
        values: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if run_kind is not _UNSET:
            updates.append("run_kind = ?")
            values.append(run_kind)
        if project_id is not _UNSET:
            updates.append("project_id = ?")
            values.append(project_id)
        if protocol_run_id is not _UNSET:
            updates.append("protocol_run_id = ?")
            values.append(protocol_run_id)
        if step_run_id is not _UNSET:
            updates.append("step_run_id = ?")
            values.append(step_run_id)
        if queue is not _UNSET:
            updates.append("queue = ?")
            values.append(queue)
        if attempt is not _UNSET:
            updates.append("attempt = ?")
            values.append(attempt)
        if worker_id is not _UNSET:
            updates.append("worker_id = ?")
            values.append(worker_id)
        if prompt_version is not _UNSET:
            updates.append("prompt_version = ?")
            values.append(prompt_version)
        if params is not _UNSET:
            updates.append("params = ?")
            values.append(json.dumps(params) if params is not None else None)
        if result is not _UNSET:
            updates.append("result = ?")
            values.append(json.dumps(result) if result is not None else None)
        if error is not _UNSET:
            updates.append("error = ?")
            values.append(error)
        if log_path is not _UNSET:
            updates.append("log_path = ?")
            values.append(log_path)
        if cost_tokens is not _UNSET:
            updates.append("cost_tokens = ?")
            values.append(cost_tokens)
        if cost_cents is not _UNSET:
            updates.append("cost_cents = ?")
            values.append(cost_cents)
        if started_at is not _UNSET:
            updates.append("started_at = ?")
            values.append(started_at)
        if finished_at is not _UNSET:
            updates.append("finished_at = ?")
            values.append(finished_at)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        set_clause = ", ".join(updates)
        values.append(run_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE codex_runs SET {set_clause} WHERE run_id = ?", tuple(values))
            conn.commit()
        return self.get_codex_run(run_id)

    def get_codex_run(self, run_id: str) -> CodexRun:
        row = self._fetchone("SELECT * FROM codex_runs WHERE run_id = ?", (run_id,))
        if row is None:
            raise KeyError(f"Codex run {run_id} not found")
        return self._row_to_codex_run(row)

    def list_codex_runs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        run_kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[CodexRun]:
        limit = max(1, min(int(limit), 500))
        base = "SELECT * FROM codex_runs"
        params: list[Any] = []
        where: list[str] = []
        if job_type:
            where.append("job_type = ?")
            params.append(job_type)
        if status:
            where.append("status = ?")
            params.append(status)
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if protocol_run_id is not None:
            where.append("protocol_run_id = ?")
            params.append(protocol_run_id)
        if step_run_id is not None:
            where.append("step_run_id = ?")
            params.append(step_run_id)
        if run_kind:
            where.append("run_kind = ?")
            params.append(run_kind)
        if where:
            base += " WHERE " + " AND ".join(where)
        base += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [self._row_to_codex_run(row) for row in rows]

    def upsert_run_artifact(
        self,
        run_id: str,
        name: str,
        *,
        kind: str,
        path: str,
        sha256: Optional[str] = None,
        bytes: Optional[int] = None,
    ) -> RunArtifact:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO run_artifacts (run_id, name, kind, path, sha256, bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, name) DO UPDATE SET
                    kind=excluded.kind,
                    path=excluded.path,
                    sha256=excluded.sha256,
                    bytes=excluded.bytes
                """,
                (run_id, name, kind, path, sha256, bytes),
            )
            artifact_id = cur.lastrowid
            conn.commit()
        # For conflict updates, lastrowid may be 0; fetch by (run_id, name).
        row = self._fetchone(
            "SELECT * FROM run_artifacts WHERE run_id = ? AND name = ? ORDER BY created_at DESC LIMIT 1",
            (run_id, name),
        )
        return self._row_to_run_artifact(row)  # type: ignore[arg-type]

    def list_run_artifacts(self, run_id: str, *, kind: Optional[str] = None, limit: int = 100) -> List[RunArtifact]:
        limit = max(1, min(int(limit), 500))
        base = "SELECT * FROM run_artifacts WHERE run_id = ?"
        params: list[Any] = [run_id]
        if kind:
            base += " AND kind = ?"
            params.append(kind)
        base += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [self._row_to_run_artifact(row) for row in rows]

    def get_run_artifact(self, artifact_id: int) -> RunArtifact:
        row = self._fetchone("SELECT * FROM run_artifacts WHERE id = ?", (artifact_id,))
        if row is None:
            raise KeyError(f"RunArtifact {artifact_id} not found")
        return self._row_to_run_artifact(row)

    @staticmethod
    def _parse_json(value: Any) -> Optional[dict]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value  # already decoded
        try:
            return json.loads(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_ts(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return value

    @staticmethod
    def _row_to_project(row: Any) -> Project:
        default_models = Database._parse_json(row["default_models"])
        secrets = Database._parse_json(row["secrets"])
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        policy_overrides = Database._parse_json(row["policy_overrides"]) if "policy_overrides" in keys else None
        policy_repo_local_enabled: Optional[bool] = None
        if "policy_repo_local_enabled" in keys and row["policy_repo_local_enabled"] is not None:
            try:
                policy_repo_local_enabled = bool(int(row["policy_repo_local_enabled"]))
            except Exception:
                policy_repo_local_enabled = bool(row["policy_repo_local_enabled"])
        return Project(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            local_path=row["local_path"] if "local_path" in set(row.keys()) else None,
            base_branch=row["base_branch"],
            ci_provider=row["ci_provider"],
            secrets=secrets,
            default_models=default_models,
            project_classification=row["project_classification"] if "project_classification" in keys else None,
            policy_pack_key=row["policy_pack_key"] if "policy_pack_key" in keys else None,
            policy_pack_version=row["policy_pack_version"] if "policy_pack_version" in keys else None,
            policy_overrides=policy_overrides,
            policy_repo_local_enabled=policy_repo_local_enabled,
            policy_effective_hash=row["policy_effective_hash"] if "policy_effective_hash" in keys else None,
            policy_enforcement_mode=row["policy_enforcement_mode"] if "policy_enforcement_mode" in keys else None,
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_protocol(row: Any) -> ProtocolRun:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        template_config = Database._parse_json(row["template_config"]) if "template_config" in keys else None  # type: ignore[arg-type]
        template_source = Database._parse_json(row["template_source"]) if "template_source" in keys else None  # type: ignore[arg-type]
        policy_effective_json = Database._parse_json(row["policy_effective_json"]) if "policy_effective_json" in keys else None  # type: ignore[arg-type]
        return ProtocolRun(
            id=row["id"],
            project_id=row["project_id"],
            protocol_name=row["protocol_name"],
            status=row["status"],
            base_branch=row["base_branch"],
            worktree_path=row["worktree_path"],
            protocol_root=row["protocol_root"],
            description=row["description"],
            template_config=template_config,
            template_source=template_source,
            policy_pack_key=row["policy_pack_key"] if "policy_pack_key" in keys else None,
            policy_pack_version=row["policy_pack_version"] if "policy_pack_version" in keys else None,
            policy_effective_hash=row["policy_effective_hash"] if "policy_effective_hash" in keys else None,
            policy_effective_json=policy_effective_json,
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_policy_pack(row: Any) -> PolicyPack:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        pack_val = Database._parse_json(row["pack"]) if "pack" in keys else None
        return PolicyPack(
            id=row["id"],
            key=row["key"],
            version=row["version"],
            name=row["name"],
            description=row["description"] if "description" in keys else None,
            status=row["status"] if "status" in keys else "active",
            pack=pack_val or {},
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_clarification(row: Any) -> Clarification:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        recommended = Database._parse_json(row["recommended"]) if "recommended" in keys else None
        options = Database._parse_json(row["options"]) if "options" in keys else None
        answer = Database._parse_json(row["answer"]) if "answer" in keys else None
        blocking_val = row["blocking"] if "blocking" in keys else 0
        try:
            blocking = bool(int(blocking_val))
        except Exception:
            blocking = bool(blocking_val)
        answered_at = None
        if "answered_at" in keys:
            try:
                raw = row["answered_at"]
            except Exception:
                raw = None
            if raw is not None:
                answered_at = Database._coerce_ts(raw)
        return Clarification(
            id=row["id"],
            scope=row["scope"],
            project_id=row["project_id"],
            protocol_run_id=row["protocol_run_id"] if "protocol_run_id" in keys else None,
            step_run_id=row["step_run_id"] if "step_run_id" in keys else None,
            key=row["key"],
            question=row["question"],
            recommended=recommended if isinstance(recommended, dict) else None,
            options=options if isinstance(options, list) else None,
            applies_to=row["applies_to"] if "applies_to" in keys else None,
            blocking=blocking,
            answer=answer if isinstance(answer, dict) else None,
            status=row["status"] if "status" in keys else "open",
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
            answered_at=answered_at,
            answered_by=row["answered_by"] if "answered_by" in keys else None,
        )

    def upsert_policy_pack(
        self,
        *,
        key: str,
        version: str,
        name: str,
        description: Optional[str],
        status: str,
        pack: dict,
    ) -> PolicyPack:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO policy_packs (key, version, name, description, status, pack)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key, version) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    status=excluded.status,
                    pack=excluded.pack,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, version, name, description, status, json.dumps(pack)),
            )
            conn.commit()
        row = self._fetchone(
            "SELECT * FROM policy_packs WHERE key = ? AND version = ? LIMIT 1",
            (key, version),
        )
        if row is None:
            raise KeyError(f"PolicyPack {key}@{version} not found after upsert")
        return self._row_to_policy_pack(row)

    def list_policy_packs(self, *, key: Optional[str] = None, status: Optional[str] = None) -> List[PolicyPack]:
        query = "SELECT * FROM policy_packs"
        params: list[Any] = []
        where: list[str] = []
        if key:
            where.append("key = ?")
            params.append(key)
        if status:
            where.append("status = ?")
            params.append(status)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY key ASC, created_at DESC"
        rows = self._fetchall(query, tuple(params))
        return [self._row_to_policy_pack(r) for r in rows]

    def get_policy_pack(self, *, key: str, version: Optional[str] = None) -> PolicyPack:
        if version:
            row = self._fetchone("SELECT * FROM policy_packs WHERE key = ? AND version = ? LIMIT 1", (key, version))
            if row is None:
                raise KeyError(f"PolicyPack {key}@{version} not found")
            return self._row_to_policy_pack(row)
        row = self._fetchone(
            "SELECT * FROM policy_packs WHERE key = ? AND status = 'active' ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT 1",
            (key,),
        )
        if row is None:
            row = self._fetchone(
                "SELECT * FROM policy_packs WHERE key = ? ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT 1",
                (key,),
            )
        if row is None:
            raise KeyError(f"PolicyPack {key} not found")
        return self._row_to_policy_pack(row)

    def _ensure_default_policy_pack_sqlite(self, conn: sqlite3.Connection) -> None:
        seed = [
            (DEFAULT_POLICY_PACK_KEY, DEFAULT_POLICY_PACK_VERSION, DEFAULT_POLICY_PACK),
            (BEGINNER_GUIDED_POLICY_PACK_KEY, BEGINNER_GUIDED_POLICY_PACK_VERSION, BEGINNER_GUIDED_POLICY_PACK),
            (STARTUP_FAST_POLICY_PACK_KEY, STARTUP_FAST_POLICY_PACK_VERSION, STARTUP_FAST_POLICY_PACK),
            (TEAM_STANDARD_POLICY_PACK_KEY, TEAM_STANDARD_POLICY_PACK_VERSION, TEAM_STANDARD_POLICY_PACK),
            (ENTERPRISE_COMPLIANCE_POLICY_PACK_KEY, ENTERPRISE_COMPLIANCE_POLICY_PACK_VERSION, ENTERPRISE_COMPLIANCE_POLICY_PACK),
        ]
        for key, version, pack in seed:
            conn.execute(
                """
                INSERT INTO policy_packs (key, version, name, description, status, pack)
                VALUES (?, ?, ?, ?, 'active', ?)
                ON CONFLICT(key, version) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    status=excluded.status,
                    pack=excluded.pack,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    key,
                    version,
                    pack["meta"]["name"],
                    pack["meta"].get("description"),
                    json.dumps(pack),
                ),
            )

    @staticmethod
    def _row_to_step(row: Any) -> StepRun:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        policy = Database._parse_json(row["policy"]) if "policy" in keys else None
        runtime_state = Database._parse_json(row["runtime_state"]) if "runtime_state" in keys else None
        return StepRun(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            step_type=row["step_type"],
            status=row["status"],
            retries=row["retries"],
            model=row["model"],
            engine_id=row["engine_id"] if "engine_id" in keys else None,
            policy=policy,
            runtime_state=runtime_state,
            summary=row["summary"],
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_codex_run(row: Any) -> CodexRun:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        return CodexRun(
            run_id=row["run_id"],
            job_type=row["job_type"],
            status=row["status"],
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
            run_kind=row["run_kind"] if "run_kind" in keys else None,
            project_id=row["project_id"] if "project_id" in keys else None,
            protocol_run_id=row["protocol_run_id"] if "protocol_run_id" in keys else None,
            step_run_id=row["step_run_id"] if "step_run_id" in keys else None,
            queue=row["queue"] if "queue" in keys else None,
            attempt=row["attempt"] if "attempt" in keys else None,
            worker_id=row["worker_id"] if "worker_id" in keys else None,
            started_at=Database._coerce_ts(row["started_at"]) if "started_at" in keys and row["started_at"] is not None else None,
            finished_at=Database._coerce_ts(row["finished_at"]) if "finished_at" in keys and row["finished_at"] is not None else None,
            prompt_version=row["prompt_version"] if "prompt_version" in keys else None,
            params=Database._parse_json(row["params"]) if "params" in keys else None,
            result=Database._parse_json(row["result"]) if "result" in keys else None,
            error=row["error"] if "error" in keys else None,
            log_path=row["log_path"] if "log_path" in keys else None,
            cost_tokens=row["cost_tokens"] if "cost_tokens" in keys else None,
            cost_cents=row["cost_cents"] if "cost_cents" in keys else None,
        )

    @staticmethod
    def _row_to_run_artifact(row: Any) -> RunArtifact:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        return RunArtifact(
            id=row["id"],
            run_id=row["run_id"],
            name=row["name"],
            kind=row["kind"],
            path=row["path"],
            sha256=row["sha256"] if "sha256" in keys else None,
            bytes=row["bytes"] if "bytes" in keys else None,
            created_at=Database._coerce_ts(row["created_at"]),
        )
    @staticmethod
    def _row_to_event(row: Any) -> Event:
        protocol_name = None
        project_id = None
        project_name = None
        if isinstance(row, dict):
            protocol_name = row.get("protocol_name")
            project_id = row.get("project_id")
            project_name = row.get("project_name")
        elif hasattr(row, "keys"):
            keys = set(row.keys())
            if "protocol_name" in keys:
                protocol_name = row["protocol_name"]
            if "project_id" in keys:
                project_id = row["project_id"]
            if "project_name" in keys:
                project_name = row["project_name"]
        return Event(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            event_type=row["event_type"],
            message=row["message"],
            metadata=Database._parse_json(row.get("metadata") if isinstance(row, dict) else row["metadata"]),
            created_at=Database._coerce_ts(row["created_at"]),
            protocol_name=protocol_name,
            project_id=project_id,
            project_name=project_name,
        )


class PostgresDatabase:
    """
    Postgres-backed persistence for orchestrator state.
    Requires psycopg>=3. Follows the same contract as the SQLite Database class.
    """

    def __init__(self, db_url: str, pool_size: int = 5):
        if psycopg is None:  # pragma: no cover - optional dependency
            raise ImportError("psycopg is required for Postgres support. Install psycopg[binary].")
        self.db_url = db_url
        self.row_factory = dict_row
        self.pool = None
        if ConnectionPool:
            # Ensure we always get dicts back from cursors when using pooled connections.
            self.pool = ConnectionPool(
                conninfo=db_url,
                min_size=1,
                max_size=pool_size,
                kwargs={"row_factory": self.row_factory},
            )

    def _connect(self):
        if self.pool:
            conn = self.pool.connection()
        else:
            conn = psycopg.connect(self.db_url, row_factory=self.row_factory)
        # Defensive: pool connections should already have the row factory set via kwargs,
        # but set it here to be sure.
        if self.row_factory is not None:
            conn.row_factory = self.row_factory
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_POSTGRES)
                try:
                    cur.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='projects' AND column_name='local_path'"
                    )
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE projects ADD COLUMN local_path TEXT")
                except Exception:
                    pass
                try:
                    project_migrations: list[tuple[str, str]] = [
                        ("project_classification", "TEXT"),
                        ("policy_pack_key", "TEXT"),
                        ("policy_pack_version", "TEXT"),
                        ("policy_overrides", "JSONB"),
                        ("policy_repo_local_enabled", "BOOLEAN"),
                        ("policy_effective_hash", "TEXT"),
                        ("policy_enforcement_mode", "TEXT"),
                    ]
                    for col_name, col_type in project_migrations:
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name='projects' AND column_name=%s",
                            (col_name,),
                        )
                        if not cur.fetchone():
                            cur.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass
                try:
                    migrations: list[tuple[str, str]] = [
                        ("run_kind", "TEXT"),
                        ("project_id", "INTEGER"),
                        ("protocol_run_id", "INTEGER"),
                        ("step_run_id", "INTEGER"),
                        ("queue", "TEXT"),
                        ("attempt", "INTEGER"),
                        ("worker_id", "TEXT"),
                    ]
                    for col_name, col_type in migrations:
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name='codex_runs' AND column_name=%s",
                            (col_name,),
                        )
                        if not cur.fetchone():
                            cur.execute(f"ALTER TABLE codex_runs ADD COLUMN {col_name} {col_type}")

                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_codex_runs_project ON codex_runs(project_id, created_at)"
                    )
                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_codex_runs_protocol ON codex_runs(protocol_run_id, created_at)"
                    )
                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_codex_runs_step ON codex_runs(step_run_id, created_at)"
                    )
                except Exception:
                    pass
                try:
                    protocol_migrations: list[tuple[str, str]] = [
                        ("policy_pack_key", "TEXT"),
                        ("policy_pack_version", "TEXT"),
                        ("policy_effective_hash", "TEXT"),
                        ("policy_effective_json", "JSONB"),
                    ]
                    for col_name, col_type in protocol_migrations:
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name='protocol_runs' AND column_name=%s",
                            (col_name,),
                        )
                        if not cur.fetchone():
                            cur.execute(f"ALTER TABLE protocol_runs ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass
            conn.commit()
        # Seed should run outside the cursor scope to keep it simple.
        try:
            self.upsert_policy_pack(
                key=DEFAULT_POLICY_PACK_KEY,
                version=DEFAULT_POLICY_PACK_VERSION,
                name=str(DEFAULT_POLICY_PACK["meta"]["name"]),
                description=str(DEFAULT_POLICY_PACK["meta"].get("description") or ""),
                status="active",
                pack=DEFAULT_POLICY_PACK,
            )
            self.upsert_policy_pack(
                key=BEGINNER_GUIDED_POLICY_PACK_KEY,
                version=BEGINNER_GUIDED_POLICY_PACK_VERSION,
                name=str(BEGINNER_GUIDED_POLICY_PACK["meta"]["name"]),
                description=str(BEGINNER_GUIDED_POLICY_PACK["meta"].get("description") or ""),
                status="active",
                pack=BEGINNER_GUIDED_POLICY_PACK,
            )
            self.upsert_policy_pack(
                key=STARTUP_FAST_POLICY_PACK_KEY,
                version=STARTUP_FAST_POLICY_PACK_VERSION,
                name=str(STARTUP_FAST_POLICY_PACK["meta"]["name"]),
                description=str(STARTUP_FAST_POLICY_PACK["meta"].get("description") or ""),
                status="active",
                pack=STARTUP_FAST_POLICY_PACK,
            )
            self.upsert_policy_pack(
                key=TEAM_STANDARD_POLICY_PACK_KEY,
                version=TEAM_STANDARD_POLICY_PACK_VERSION,
                name=str(TEAM_STANDARD_POLICY_PACK["meta"]["name"]),
                description=str(TEAM_STANDARD_POLICY_PACK["meta"].get("description") or ""),
                status="active",
                pack=TEAM_STANDARD_POLICY_PACK,
            )
            self.upsert_policy_pack(
                key=ENTERPRISE_COMPLIANCE_POLICY_PACK_KEY,
                version=ENTERPRISE_COMPLIANCE_POLICY_PACK_VERSION,
                name=str(ENTERPRISE_COMPLIANCE_POLICY_PACK["meta"]["name"]),
                description=str(ENTERPRISE_COMPLIANCE_POLICY_PACK["meta"].get("description") or ""),
                status="active",
                pack=ENTERPRISE_COMPLIANCE_POLICY_PACK,
            )
        except Exception:
            pass
        # Backfill existing projects to a default policy selection (rollout safety).
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE projects
                        SET policy_pack_key = COALESCE(policy_pack_key, %s),
                            policy_pack_version = COALESCE(policy_pack_version, %s),
                            policy_repo_local_enabled = COALESCE(policy_repo_local_enabled, false),
                            policy_enforcement_mode = COALESCE(policy_enforcement_mode, 'warn')
                        """,
                        (DEFAULT_POLICY_PACK_KEY, DEFAULT_POLICY_PACK_VERSION),
                    )
                conn.commit()
        except Exception:
            pass

    def _fetchone(self, query: str, params: Iterable[Any]) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
        return row

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return rows or []

    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str],
        default_models: Optional[dict],
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project:
        normalized_classification, effective_pack_key, effective_pack_version = _resolve_policy_selection(
            project_classification=project_classification,
            policy_pack_key=policy_pack_key,
            policy_pack_version=policy_pack_version,
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                default_models_json = json.dumps(default_models) if default_models is not None else None
                secrets_json = json.dumps(secrets) if secrets is not None else None
                cur.execute(
                    """
                    INSERT INTO projects (
                        name,
                        git_url,
                        base_branch,
                        ci_provider,
                        project_classification,
                        default_models,
                        secrets,
                        local_path,
                        policy_pack_key,
                        policy_pack_version,
                        policy_overrides,
                        policy_repo_local_enabled,
                        policy_effective_hash,
                        policy_enforcement_mode
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        name,
                        git_url,
                        base_branch,
                        ci_provider,
                        normalized_classification,
                        default_models_json,
                        secrets_json,
                        local_path,
                        effective_pack_key,
                        effective_pack_version,
                        None,
                        False,
                        None,
                        "warn",
                    ),
                )
                project_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_project(project_id)

    def update_project_policy(
        self,
        project_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        clear_policy_pack_version: bool = False,
        policy_overrides: Optional[dict] = None,
        policy_repo_local_enabled: Optional[bool] = None,
        policy_effective_hash: Optional[str] = None,
        policy_enforcement_mode: Optional[str] = None,
    ) -> Project:
        updates: list[str] = []
        values: list[Any] = []
        if policy_pack_key is not None:
            updates.append("policy_pack_key = %s")
            values.append(policy_pack_key)
        if clear_policy_pack_version:
            updates.append("policy_pack_version = %s")
            values.append(None)
        elif policy_pack_version is not None:
            updates.append("policy_pack_version = %s")
            values.append(policy_pack_version)
        if policy_overrides is not None:
            updates.append("policy_overrides = %s")
            values.append(json.dumps(policy_overrides))
        if policy_repo_local_enabled is not None:
            updates.append("policy_repo_local_enabled = %s")
            values.append(bool(policy_repo_local_enabled))
        if policy_effective_hash is not None:
            updates.append("policy_effective_hash = %s")
            values.append(policy_effective_hash)
        if policy_enforcement_mode is not None:
            updates.append("policy_enforcement_mode = %s")
            values.append(policy_enforcement_mode)
        if not updates:
            return self.get_project(project_id)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(project_id)
        set_clause = ", ".join(updates)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE projects SET {set_clause} WHERE id = %s", tuple(values))
            conn.commit()
        return self.get_project(project_id)

    def upsert_clarification(
        self,
        *,
        scope: str,
        project_id: int,
        key: str,
        question: str,
        recommended: Optional[dict] = None,
        options: Optional[list] = None,
        applies_to: Optional[str] = None,
        blocking: bool = False,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
    ) -> Clarification:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clarifications (
                        scope, project_id, protocol_run_id, step_run_id,
                        key, question, recommended, options, applies_to, blocking, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')
                    ON CONFLICT(scope, key) DO UPDATE SET
                        project_id=excluded.project_id,
                        protocol_run_id=excluded.protocol_run_id,
                        step_run_id=excluded.step_run_id,
                        question=excluded.question,
                        recommended=excluded.recommended,
                        options=excluded.options,
                        applies_to=excluded.applies_to,
                        blocking=excluded.blocking,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING *
                    """,
                    (
                        scope,
                        project_id,
                        protocol_run_id,
                        step_run_id,
                        key,
                        question,
                        json.dumps(recommended) if recommended is not None else None,
                        json.dumps(options) if options is not None else None,
                        applies_to,
                        bool(blocking),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            raise KeyError("Clarification not found after upsert")
        return self._row_to_clarification(row)

    def list_clarifications(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        status: Optional[str] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM clarifications"
        where: list[str] = []
        values: list[Any] = []
        if project_id is not None:
            where.append("project_id = %s")
            values.append(project_id)
        if protocol_run_id is not None:
            where.append("protocol_run_id = %s")
            values.append(protocol_run_id)
        if step_run_id is not None:
            where.append("step_run_id = %s")
            values.append(step_run_id)
        if status:
            where.append("status = %s")
            values.append(status)
        if applies_to:
            where.append("applies_to = %s")
            values.append(applies_to)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT %s"
        values.append(limit)
        rows = self._fetchall(query, tuple(values))
        return [self._row_to_clarification(r) for r in rows]

    def answer_clarification(
        self,
        *,
        scope: str,
        key: str,
        answer: Optional[dict],
        answered_by: Optional[str] = None,
        status: str = "answered",
    ) -> Clarification:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE clarifications
                    SET answer = %s,
                        status = %s,
                        answered_at = CURRENT_TIMESTAMP,
                        answered_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE scope = %s AND key = %s
                    RETURNING *
                    """,
                    (
                        json.dumps(answer) if answer is not None else None,
                        status,
                        answered_by,
                        scope,
                        key,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            raise KeyError(f"Clarification {scope}:{key} not found")
        return self._row_to_clarification(row)

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE projects SET local_path = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (local_path, project_id),
                )
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return Database._row_to_project(row)  # type: ignore[arg-type]

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [Database._row_to_project(row) for row in rows]  # type: ignore[arg-type]

    def update_protocol_policy_audit(
        self,
        run_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        policy_effective_hash: Optional[str] = None,
        policy_effective_json: Optional[dict] = None,
    ) -> ProtocolRun:
        updates: list[str] = []
        values: list[Any] = []
        if policy_pack_key is not None:
            updates.append("policy_pack_key = %s")
            values.append(policy_pack_key)
        if policy_pack_version is not None:
            updates.append("policy_pack_version = %s")
            values.append(policy_pack_version)
        if policy_effective_hash is not None:
            updates.append("policy_effective_hash = %s")
            values.append(policy_effective_hash)
        if policy_effective_json is not None:
            updates.append("policy_effective_json = %s")
            values.append(json.dumps(policy_effective_json))
        if not updates:
            return self.get_protocol_run(run_id)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(run_id)
        set_clause = ", ".join(updates)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE protocol_runs SET {set_clause} WHERE id = %s", tuple(values))
            conn.commit()
        return self.get_protocol_run(run_id)

    def upsert_policy_pack(
        self,
        *,
        key: str,
        version: str,
        name: str,
        description: Optional[str],
        status: str,
        pack: dict,
    ) -> PolicyPack:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO policy_packs (key, version, name, description, status, pack)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(key, version) DO UPDATE SET
                        name=EXCLUDED.name,
                        description=EXCLUDED.description,
                        status=EXCLUDED.status,
                        pack=EXCLUDED.pack,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (key, version, name, description, status, json.dumps(pack)),
                )
                pack_id = cur.fetchone()["id"]
            conn.commit()
        row = self._fetchone("SELECT * FROM policy_packs WHERE id = %s", (pack_id,))
        if row is None:
            raise KeyError(f"PolicyPack {key}@{version} not found after upsert")
        return Database._row_to_policy_pack(row)  # type: ignore[arg-type]

    def list_policy_packs(self, *, key: Optional[str] = None, status: Optional[str] = None) -> List[PolicyPack]:
        query = "SELECT * FROM policy_packs"
        params: list[Any] = []
        where: list[str] = []
        if key:
            where.append("key = %s")
            params.append(key)
        if status:
            where.append("status = %s")
            params.append(status)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY key ASC, created_at DESC"
        rows = self._fetchall(query, tuple(params))
        return [Database._row_to_policy_pack(r) for r in rows]  # type: ignore[arg-type]

    def get_policy_pack(self, *, key: str, version: Optional[str] = None) -> PolicyPack:
        if version:
            row = self._fetchone("SELECT * FROM policy_packs WHERE key = %s AND version = %s LIMIT 1", (key, version))
            if row is None:
                raise KeyError(f"PolicyPack {key}@{version} not found")
            return Database._row_to_policy_pack(row)  # type: ignore[arg-type]
        row = self._fetchone(
            "SELECT * FROM policy_packs WHERE key = %s AND status = 'active' ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT 1",
            (key,),
        )
        if row is None:
            row = self._fetchone(
                "SELECT * FROM policy_packs WHERE key = %s ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT 1",
                (key,),
            )
        if row is None:
            raise KeyError(f"PolicyPack {key} not found")
        return Database._row_to_policy_pack(row)  # type: ignore[arg-type]

    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str],
        protocol_root: Optional[str],
        description: Optional[str],
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO protocol_runs (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description, template_config, template_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        project_id,
                        protocol_name,
                        status,
                        base_branch,
                        worktree_path,
                        protocol_root,
                        description,
                        json.dumps(template_config) if template_config is not None else None,
                        json.dumps(template_source) if template_source is not None else None,
                    ),
                )
                run_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = %s", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return Database._row_to_protocol(row)  # type: ignore[arg-type]

    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = %s", (protocol_name,))
        return Database._row_to_protocol(row) if row else None  # type: ignore[arg-type]

    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]:
        ref = branch.replace("refs/heads/", "").replace("refs/tags/", "")
        parts = ref.split("/")
        candidates = [ref, parts[-1]]
        for cand in candidates:
            row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = %s", (cand,))
            if row:
                return Database._row_to_protocol(row)  # type: ignore[arg-type]
        return None

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = %s ORDER BY created_at DESC",
            (project_id,),
        )
        return [Database._row_to_protocol(row) for row in rows]  # type: ignore[arg-type]

    def list_all_protocol_runs(self) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs ORDER BY created_at DESC",
        )
        return [Database._row_to_protocol(row) for row in rows]  # type: ignore[arg-type]

    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if expected_status:
                    cur.execute(
                        "UPDATE protocol_runs SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = %s",
                        (status, run_id, expected_status),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(f"ProtocolRun {run_id} status conflict")
                else:
                    cur.execute(
                        "UPDATE protocol_runs SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (status, run_id),
                    )
        conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE protocol_runs
                    SET template_config = %s, template_source = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        json.dumps(template_config) if template_config is not None else None,
                        json.dumps(template_source) if template_source is not None else None,
                        run_id,
                    ),
                )
            conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE protocol_runs
                    SET worktree_path = %s, protocol_root = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (worktree_path, protocol_root, run_id),
                )
            conn.commit()
        return self.get_protocol_run(run_id)

    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        model: Optional[str],
        engine_id: Optional[str] = None,
        retries: int = 0,
        summary: Optional[str] = None,
        policy: Optional[dict] = None,
    ) -> StepRun:
        policy_json = json.dumps(policy) if policy is not None else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO step_runs (protocol_run_id, step_index, step_name, step_type, status, model, engine_id, policy, runtime_state, summary, retries)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        protocol_run_id,
                        step_index,
                        step_name,
                        step_type,
                        status,
                        model,
                        engine_id,
                        policy_json,
                        None,
                        summary,
                        retries,
                    ),
                )
                step_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_step_run(step_id)

    def get_step_run(self, step_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = %s", (step_id,))
        if row is None:
            raise KeyError(f"StepRun {step_id} not found")
        return Database._row_to_step(row)  # type: ignore[arg-type]

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = %s ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [Database._row_to_step(row) for row in rows]  # type: ignore[arg-type]

    def list_all_step_runs(self) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs ORDER BY created_at DESC",
        )
        return [Database._row_to_step(row) for row in rows]  # type: ignore[arg-type]

    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]:
        row = self._fetchone(
            "SELECT * FROM step_runs WHERE protocol_run_id = %s ORDER BY updated_at DESC, created_at DESC LIMIT 1",
            (protocol_run_id,),
        )
        return Database._row_to_step(row) if row else None  # type: ignore[arg-type]

    def update_step_status(
        self,
        step_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
        expected_status: Optional[str] = None,
    ) -> StepRun:
        runtime_state_json = json.dumps(runtime_state) if runtime_state is not None else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                if expected_status:
                    cur.execute(
                        """
                        UPDATE step_runs
                        SET status = %s,
                            summary = COALESCE(%s, summary),
                            model = COALESCE(%s, model),
                            engine_id = COALESCE(%s, engine_id),
                            runtime_state = COALESCE(%s, runtime_state),
                            retries = COALESCE(%s, retries),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND status = %s
                        """,
                        (status, summary, model, engine_id, runtime_state_json, retries, step_id, expected_status),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(f"StepRun {step_id} status conflict")
                else:
                    cur.execute(
                        """
                        UPDATE step_runs
                        SET status = %s,
                            summary = COALESCE(%s, summary),
                            model = COALESCE(%s, model),
                            engine_id = COALESCE(%s, engine_id),
                            runtime_state = COALESCE(%s, runtime_state),
                            retries = COALESCE(%s, retries),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (status, summary, model, engine_id, runtime_state_json, retries, step_id),
                    )
            conn.commit()
        return self.get_step_run(step_id)

    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        step_run_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Event:
        meta = dict(metadata or {})
        if request_id and "request_id" not in meta:
            meta["request_id"] = request_id
        if job_id and "job_id" not in meta:
            meta["job_id"] = job_id
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (protocol_run_id, step_run_id, event_type, message, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (protocol_run_id, step_run_id, event_type, message, json.dumps(meta) if meta else None),
                )
                event_id = cur.fetchone()["id"]
            conn.commit()
        row = self._fetchone("SELECT * FROM events WHERE id = %s", (event_id,))
        return Database._row_to_event(row)  # type: ignore[arg-type]

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = %s ORDER BY created_at DESC",
            (protocol_run_id,),
        )
        return [Database._row_to_event(row) for row in rows]  # type: ignore[arg-type]

    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]:
        limit = max(1, min(int(limit), 500))
        base = """
        SELECT e.*, pr.protocol_name, pr.project_id, p.name AS project_name
        FROM events e
        JOIN protocol_runs pr ON e.protocol_run_id = pr.id
        JOIN projects p ON pr.project_id = p.id
        """
        params: list[Any] = []
        if project_id is not None:
            base += " WHERE pr.project_id = %s"
            params.append(project_id)
        base += " ORDER BY e.created_at DESC LIMIT %s"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [Database._row_to_event(row) for row in rows]  # type: ignore[arg-type]

    def create_codex_run(
        self,
        run_id: str,
        job_type: str,
        status: str,
        *,
        run_kind: Optional[str] = None,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        queue: Optional[str] = None,
        attempt: Optional[int] = None,
        worker_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        params: Optional[dict] = None,
        log_path: Optional[str] = None,
        started_at: Optional[str] = None,
        cost_tokens: Optional[int] = None,
        cost_cents: Optional[int] = None,
    ) -> CodexRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO codex_runs (
                        run_id,
                        job_type,
                        status,
                        run_kind,
                        project_id,
                        protocol_run_id,
                        step_run_id,
                        queue,
                        attempt,
                        worker_id,
                        prompt_version,
                        params,
                        log_path,
                        started_at,
                        cost_tokens,
                        cost_cents
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING run_id
                    """,
                    (
                        run_id,
                        job_type,
                        status,
                        run_kind,
                        project_id,
                        protocol_run_id,
                        step_run_id,
                        queue,
                        attempt,
                        worker_id,
                        prompt_version,
                        json.dumps(params) if params is not None else None,
                        log_path,
                        started_at,
                        cost_tokens,
                        cost_cents,
                    ),
                )
            conn.commit()
        return self.get_codex_run(run_id)

    def update_codex_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        run_kind: Any = _UNSET,
        project_id: Any = _UNSET,
        protocol_run_id: Any = _UNSET,
        step_run_id: Any = _UNSET,
        queue: Any = _UNSET,
        attempt: Any = _UNSET,
        worker_id: Any = _UNSET,
        prompt_version: Any = _UNSET,
        params: Any = _UNSET,
        result: Any = _UNSET,
        error: Any = _UNSET,
        log_path: Any = _UNSET,
        cost_tokens: Any = _UNSET,
        cost_cents: Any = _UNSET,
        started_at: Any = _UNSET,
        finished_at: Any = _UNSET,
    ) -> CodexRun:
        updates: list[str] = []
        values: list[Any] = []
        if status is not None:
            updates.append("status = %s")
            values.append(status)
        if run_kind is not _UNSET:
            updates.append("run_kind = %s")
            values.append(run_kind)
        if project_id is not _UNSET:
            updates.append("project_id = %s")
            values.append(project_id)
        if protocol_run_id is not _UNSET:
            updates.append("protocol_run_id = %s")
            values.append(protocol_run_id)
        if step_run_id is not _UNSET:
            updates.append("step_run_id = %s")
            values.append(step_run_id)
        if queue is not _UNSET:
            updates.append("queue = %s")
            values.append(queue)
        if attempt is not _UNSET:
            updates.append("attempt = %s")
            values.append(attempt)
        if worker_id is not _UNSET:
            updates.append("worker_id = %s")
            values.append(worker_id)
        if prompt_version is not _UNSET:
            updates.append("prompt_version = %s")
            values.append(prompt_version)
        if params is not _UNSET:
            updates.append("params = %s")
            values.append(json.dumps(params) if params is not None else None)
        if result is not _UNSET:
            updates.append("result = %s")
            values.append(json.dumps(result) if result is not None else None)
        if error is not _UNSET:
            updates.append("error = %s")
            values.append(error)
        if log_path is not _UNSET:
            updates.append("log_path = %s")
            values.append(log_path)
        if cost_tokens is not _UNSET:
            updates.append("cost_tokens = %s")
            values.append(cost_tokens)
        if cost_cents is not _UNSET:
            updates.append("cost_cents = %s")
            values.append(cost_cents)
        if started_at is not _UNSET:
            updates.append("started_at = %s")
            values.append(started_at)
        if finished_at is not _UNSET:
            updates.append("finished_at = %s")
            values.append(finished_at)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        set_clause = ", ".join(updates)
        values.append(run_id)
        query = f"UPDATE codex_runs SET {set_clause} WHERE run_id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(values))
            conn.commit()
        return self.get_codex_run(run_id)

    def get_codex_run(self, run_id: str) -> CodexRun:
        row = self._fetchone("SELECT * FROM codex_runs WHERE run_id = %s", (run_id,))
        if row is None:
            raise KeyError(f"Codex run {run_id} not found")
        return Database._row_to_codex_run(row)  # type: ignore[arg-type]

    def list_codex_runs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        run_kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[CodexRun]:
        limit = max(1, min(int(limit), 500))
        base = "SELECT * FROM codex_runs"
        params: list[Any] = []
        where: list[str] = []
        if job_type:
            where.append("job_type = %s")
            params.append(job_type)
        if status:
            where.append("status = %s")
            params.append(status)
        if project_id is not None:
            where.append("project_id = %s")
            params.append(project_id)
        if protocol_run_id is not None:
            where.append("protocol_run_id = %s")
            params.append(protocol_run_id)
        if step_run_id is not None:
            where.append("step_run_id = %s")
            params.append(step_run_id)
        if run_kind:
            where.append("run_kind = %s")
            params.append(run_kind)
        if where:
            base += " WHERE " + " AND ".join(where)
        base += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [Database._row_to_codex_run(row) for row in rows]  # type: ignore[arg-type]

    def upsert_run_artifact(
        self,
        run_id: str,
        name: str,
        *,
        kind: str,
        path: str,
        sha256: Optional[str] = None,
        bytes: Optional[int] = None,
    ) -> RunArtifact:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO run_artifacts (run_id, name, kind, path, sha256, bytes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, name) DO UPDATE SET
                        kind = EXCLUDED.kind,
                        path = EXCLUDED.path,
                        sha256 = EXCLUDED.sha256,
                        bytes = EXCLUDED.bytes
                    RETURNING id
                    """,
                    (run_id, name, kind, path, sha256, bytes),
                )
                artifact_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_run_artifact(int(artifact_id))

    def list_run_artifacts(self, run_id: str, *, kind: Optional[str] = None, limit: int = 100) -> List[RunArtifact]:
        limit = max(1, min(int(limit), 500))
        base = "SELECT * FROM run_artifacts WHERE run_id = %s"
        params: list[Any] = [run_id]
        if kind:
            base += " AND kind = %s"
            params.append(kind)
        base += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [Database._row_to_run_artifact(row) for row in rows]  # type: ignore[arg-type]

    def get_run_artifact(self, artifact_id: int) -> RunArtifact:
        row = self._fetchone("SELECT * FROM run_artifacts WHERE id = %s", (artifact_id,))
        if row is None:
            raise KeyError(f"RunArtifact {artifact_id} not found")
        return Database._row_to_run_artifact(row)  # type: ignore[arg-type]


def create_database(db_path: Path, db_url: Optional[str] = None, pool_size: int = 5) -> BaseDatabase:
    """
    Factory to select the backing store. Defaults to SQLite; accepts a Postgres URL
    to allow future migrations without changing callers.
    """
    if db_url and db_url.startswith("postgres"):
        return PostgresDatabase(db_url, pool_size=pool_size)
    return Database(db_path)
