"""
DevGodzilla Database Schema Definitions

Raw SQL schema for SQLite and PostgreSQL.
These are used for non-Alembic schema initialization.
"""

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
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
    linked_sprint_id INTEGER REFERENCES sprints(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS speckit_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    spec_number INTEGER,
    feature_name TEXT,
    spec_path TEXT,
    plan_path TEXT,
    tasks_path TEXT,
    checklist_path TEXT,
    analysis_path TEXT,
    implement_path TEXT,
    has_spec INTEGER DEFAULT 0,
    has_plan INTEGER DEFAULT 0,
    has_tasks INTEGER DEFAULT 0,
    has_checklist INTEGER DEFAULT 0,
    has_analysis INTEGER DEFAULT 0,
    has_implement INTEGER DEFAULT 0,
    constitution_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS spec_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    spec_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    branch_name TEXT,
    worktree_path TEXT,
    spec_root TEXT,
    spec_number INTEGER,
    feature_name TEXT,
    spec_path TEXT,
    plan_path TEXT,
    tasks_path TEXT,
    checklist_path TEXT,
    analysis_path TEXT,
    implement_path TEXT,
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_spec_runs_project ON spec_runs(project_id, created_at);

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
    linked_task_id INTEGER REFERENCES tasks(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    process_key TEXT NOT NULL,
    agent_id TEXT,
    prompt_id TEXT,
    model_override TEXT,
    enabled INTEGER DEFAULT 1,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, process_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_assignments_project ON agent_assignments(project_id, process_key);

CREATE TABLE IF NOT EXISTS agent_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    agent_id TEXT NOT NULL,
    overrides TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, agent_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_overrides_project ON agent_overrides(project_id);

CREATE TABLE IF NOT EXISTS agent_assignment_settings (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id),
    inherit_global INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    project_id INTEGER REFERENCES projects(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_protocol ON events(protocol_run_id, created_at);

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

CREATE TABLE IF NOT EXISTS qa_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER NOT NULL REFERENCES step_runs(id),
    verdict TEXT NOT NULL,
    summary TEXT,
    gate_results TEXT,
    findings TEXT,
    prompt_path TEXT,
    prompt_hash TEXT,
    engine_id TEXT,
    model TEXT,
    report_path TEXT,
    report_text TEXT,
    duration_seconds REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qa_results_project ON qa_results(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qa_results_protocol ON qa_results(protocol_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qa_results_step ON qa_results(step_run_id, created_at);

CREATE TABLE IF NOT EXISTS sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    start_date DATETIME,
    end_date DATETIME,
    velocity_planned INTEGER,
    velocity_actual INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    sprint_id INTEGER REFERENCES sprints(id),
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    title TEXT NOT NULL,
    description TEXT,
    task_type TEXT NOT NULL DEFAULT 'story',
    priority TEXT NOT NULL DEFAULT 'medium',
    board_status TEXT NOT NULL DEFAULT 'backlog',
    story_points INTEGER,
    assignee TEXT,
    reporter TEXT,
    labels TEXT DEFAULT '[]',
    acceptance_criteria TEXT DEFAULT '[]',
    blocked_by TEXT DEFAULT '[]',
    blocks TEXT DEFAULT '[]',
    due_date DATETIME,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id, board_status);
CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
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
    linked_sprint_id INTEGER REFERENCES sprints(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS speckit_specs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    spec_number INTEGER,
    feature_name TEXT,
    spec_path TEXT,
    plan_path TEXT,
    tasks_path TEXT,
    checklist_path TEXT,
    analysis_path TEXT,
    implement_path TEXT,
    has_spec BOOLEAN DEFAULT FALSE,
    has_plan BOOLEAN DEFAULT FALSE,
    has_tasks BOOLEAN DEFAULT FALSE,
    has_checklist BOOLEAN DEFAULT FALSE,
    has_analysis BOOLEAN DEFAULT FALSE,
    has_implement BOOLEAN DEFAULT FALSE,
    constitution_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS spec_runs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    spec_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    branch_name TEXT,
    worktree_path TEXT,
    spec_root TEXT,
    spec_number INTEGER,
    feature_name TEXT,
    spec_path TEXT,
    plan_path TEXT,
    tasks_path TEXT,
    checklist_path TEXT,
    analysis_path TEXT,
    implement_path TEXT,
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_spec_runs_project ON spec_runs(project_id, created_at);

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
    linked_task_id INTEGER REFERENCES tasks(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_assignments (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    process_key TEXT NOT NULL,
    agent_id TEXT,
    prompt_id TEXT,
    model_override TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, process_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_assignments_project ON agent_assignments(project_id, process_key);

CREATE TABLE IF NOT EXISTS agent_overrides (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    agent_id TEXT NOT NULL,
    overrides JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, agent_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_overrides_project ON agent_overrides(project_id);

CREATE TABLE IF NOT EXISTS agent_assignment_settings (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id),
    inherit_global BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    project_id INTEGER REFERENCES projects(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_protocol ON events(protocol_run_id, created_at);

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

CREATE TABLE IF NOT EXISTS qa_results (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER NOT NULL REFERENCES step_runs(id),
    verdict TEXT NOT NULL,
    summary TEXT,
    gate_results JSONB,
    findings JSONB,
    prompt_path TEXT,
    prompt_hash TEXT,
    engine_id TEXT,
    model TEXT,
    report_path TEXT,
    report_text TEXT,
    duration_seconds DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qa_results_project ON qa_results(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qa_results_protocol ON qa_results(protocol_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qa_results_step ON qa_results(step_run_id, created_at);

CREATE TABLE IF NOT EXISTS sprints (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    velocity_planned INTEGER,
    velocity_actual INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    sprint_id INTEGER REFERENCES sprints(id),
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    title TEXT NOT NULL,
    description TEXT,
    task_type TEXT NOT NULL DEFAULT 'story',
    priority TEXT NOT NULL DEFAULT 'medium',
    board_status TEXT NOT NULL DEFAULT 'backlog',
    story_points INTEGER,
    assignee TEXT,
    reporter TEXT,
    labels JSONB DEFAULT '[]',
    acceptance_criteria JSONB DEFAULT '[]',
    blocked_by JSONB DEFAULT '[]',
    blocks JSONB DEFAULT '[]',
    due_date TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id, board_status);
CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
"""
