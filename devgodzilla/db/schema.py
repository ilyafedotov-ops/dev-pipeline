"""
DevGodzilla Database Schema Definitions

Raw SQL schema for SQLite and PostgreSQL.
These are used for non-Alembic schema initialization.
"""

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
    constitution_version TEXT,
    constitution_hash TEXT,
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
    windmill_flow_id TEXT,
    speckit_metadata TEXT,
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
    depends_on TEXT DEFAULT '[]',
    parallel_group TEXT,
    assigned_agent TEXT,
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

CREATE TABLE IF NOT EXISTS job_runs (
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
    cost_cents INTEGER,
    windmill_job_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_runs_job_status ON job_runs(job_type, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_project ON job_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_protocol ON job_runs(protocol_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_step ON job_runs(step_run_id, created_at);

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

CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    error_type TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    context TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_feedback_events_protocol ON feedback_events(protocol_run_id, created_at);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    local_path TEXT,
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
    constitution_version TEXT,
    constitution_hash TEXT,
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
    windmill_flow_id TEXT,
    speckit_metadata JSONB,
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
    depends_on JSONB DEFAULT '[]',
    parallel_group TEXT,
    assigned_agent TEXT,
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

CREATE TABLE IF NOT EXISTS job_runs (
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
    cost_cents INTEGER,
    windmill_job_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_runs_job_status ON job_runs(job_type, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_project ON job_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_protocol ON job_runs(protocol_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_step ON job_runs(step_run_id, created_at);

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

CREATE TABLE IF NOT EXISTS feedback_events (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    error_type TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    context JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_feedback_events_protocol ON feedback_events(protocol_run_id, created_at);
"""
