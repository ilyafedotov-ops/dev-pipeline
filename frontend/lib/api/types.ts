// Domain Models aligned with backend schemas

// =============================================================================
// Enums
// =============================================================================

export type ProtocolStatus =
  | "pending"
  | "planning"
  | "planned"
  | "running"
  | "paused"
  | "blocked"
  | "failed"
  | "cancelled"
  | "completed"

export type StepStatus = "pending" | "running" | "needs_qa" | "completed" | "failed" | "cancelled" | "blocked"

export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled"

export type ClarificationStatus = "open" | "answered"

export type PolicyEnforcementMode = "off" | "warn" | "enforce"

export type SprintStatus = "planning" | "active" | "completed" | "archived"
export type TaskPriority = "critical" | "high" | "medium" | "low"
export type TaskType = "story" | "bug" | "task" | "spike" | "epic"
export type TaskBoardStatus = "backlog" | "todo" | "in_progress" | "review" | "testing" | "done"

// =============================================================================
// Project
// =============================================================================

export interface Project {
  id: number
  name: string
  git_url: string
  local_path: string | null
  base_branch: string
  ci_provider: string | null
  project_classification: string | null
  default_models: Record<string, string> | null
  secrets: Record<string, unknown> | null
  created_at: string
  updated_at: string
  // Policy fields
  policy_pack_key: string | null
  policy_pack_version: string | null
  policy_overrides: Record<string, unknown> | null
  policy_repo_local_enabled: boolean | null
  policy_effective_hash: string | null
  policy_enforcement_mode: PolicyEnforcementMode | null
  // API fields
  status?: string | null
  constitution_version?: string | null
}

export interface ProjectCreate {
  name: string
  git_url: string
  base_branch?: string
  ci_provider?: string
  policy_pack_key?: string
}

export interface OnboardingSummary {
  project_id: number
  status: string
  stages: OnboardingStage[]
  events: OnboardingEvent[]
  blocking_clarifications: number
}

export interface OnboardingStage {
  name: string
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  started_at: string | null
  completed_at: string | null
}

export interface OnboardingEvent {
  event_type: string
  message: string
  created_at: string
}

// =============================================================================
// Protocol
// =============================================================================

export interface ProtocolRun {
  id: number
  project_id: number
  protocol_name: string
  status: ProtocolStatus
  base_branch: string
  worktree_path: string | null
  protocol_root: string | null
  description: string | null
  template_config: Record<string, unknown> | null
  template_source: string | null
  spec_hash: string | null
  spec_validation_status: string | null
  spec_validated_at: string | null
  policy_pack_key: string | null
  policy_pack_version: string | null
  policy_effective_hash: string | null
  policy_effective_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
  // Joined fields
  project_name?: string
}

export interface ProtocolCreate {
  protocol_name: string
  description?: string
  base_branch?: string
  template_source?: string
}

export interface ProtocolSpec {
  spec_hash: string
  validation_status: string
  validated_at: string | null
  spec: Record<string, unknown>
}

export interface ProtocolFromSpecRequest {
  project_id: number
  spec_path?: string | null
  tasks_path?: string | null
  protocol_name?: string | null
  spec_run_id?: number | null
  overwrite?: boolean
}

export interface ProtocolFromSpecResponse {
  success: boolean
  protocol: ProtocolRun | null
  protocol_root: string | null
  step_count: number
  warnings: string[]
  error?: string | null
}

// =============================================================================
// Step
// =============================================================================

export interface StepRun {
  id: number
  protocol_run_id: number
  step_index: number
  step_name: string
  step_type: string
  status: StepStatus
  retries: number
  model: string | null
  engine_id: string | null
  policy: Record<string, unknown> | null
  runtime_state: StepRuntimeState | null
  summary: string | null
  assigned_agent?: string | null
  depends_on?: number[] | null
  parallel_group?: string | null
  created_at: string
  updated_at: string
}

export interface StepRuntimeState {
  loop_counts: Record<string, number>
  inline_trigger_depth: number
}

// =============================================================================
// Runs (CodexRun)
// =============================================================================

export interface CodexRun {
  run_id: string
  job_type: string
  run_kind: string
  status: RunStatus
  project_id: number | null
  protocol_run_id: number | null
  step_run_id: number | null
  attempt: number
  worker_id: string | null
  queue: string | null
  prompt_version: string | null
  params: Record<string, unknown> | null
  result: Record<string, unknown> | null
  error: string | null
  log_path: string | null
  cost_tokens: number | null
  cost_cents: number | null
  windmill_job_id?: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface RunArtifact {
  id: number
  run_id: string
  name: string
  kind: string
  path: string
  sha256: string | null
  bytes: number | null
  created_at: string
  content_type?: "file" | "diff"
  diff_data?: {
    old_path?: string
    new_path?: string
    additions: number
    deletions: number
    hunks: DiffHunk[]
  }
}

export interface ArtifactContent {
  id: string
  name: string
  type: string
  content: string
  truncated: boolean
}

export interface DiffHunk {
  old_start: number
  old_lines: number
  new_start: number
  new_lines: number
  lines: DiffLine[]
}

export interface DiffLine {
  type: "add" | "delete" | "context"
  content: string
  old_line_number?: number
  new_line_number?: number
}

export interface RunFilters {
  job_type?: string
  status?: RunStatus
  run_kind?: string
  project_id?: number
  protocol_run_id?: number
  step_run_id?: number
  limit?: number
}

// =============================================================================
// Events
// =============================================================================

export interface Event {
  id: number
  protocol_run_id: number | null
  step_run_id: number | null
  event_type: string
  message: string
  metadata: Record<string, unknown> | null
  event_category?: string | null
  created_at: string
  // Joined fields
  protocol_name?: string
  project_id?: number
  project_name?: string
}

export interface EventFilters {
  project_id?: number
  protocol_run_id?: number
  event_type?: string
  categories?: string[]
  limit?: number
}

// =============================================================================
// Policy
// =============================================================================

export interface PolicyPack {
  id: number
  key: string | null
  version: string
  name: string
  description: string | null
  status: "active" | "deprecated" | "draft"
  pack: PolicyPackContent
  created_at: string
}

export interface PolicyPackContent {
  meta?: Record<string, unknown>
  defaults?: Record<string, unknown>
  requirements?: Record<string, unknown>
  clarifications?: Record<string, unknown>
  enforcement?: Record<string, unknown>
}

export interface PolicyConfig {
  policy_pack_key: string | null
  policy_pack_version: string | null
  policy_overrides: Record<string, unknown> | null
  policy_repo_local_enabled: boolean
  policy_enforcement_mode: PolicyEnforcementMode
}

export interface PolicyFinding {
  code: string
  severity: "error" | "warning" | "info"
  message: string
  location: string | null
  suggested_fix: string | null
}

export interface EffectivePolicy {
  hash: string
  policy: Record<string, unknown>
}

// =============================================================================
// Clarifications
// =============================================================================

export interface Clarification {
  id: number
  scope: string | null
  project_id: number | null
  protocol_run_id: number | null
  step_run_id: number | null
  key: string
  question: string
  recommended: Record<string, unknown> | string | null
  options: string[] | null
  applies_to: string | null
  blocking: boolean
  answer: Record<string, unknown> | string | null
  status: ClarificationStatus
  answered_at: string | null
  answered_by: string | null
}

// =============================================================================
// Operations
// =============================================================================

export interface QueueStats {
  name: string
  queued: number
  started: number
  failed: number
}

export interface QueueJob {
  job_id: string
  job_type: string
  status: "queued" | "started" | "failed"
  enqueued_at: string
  started_at: string | null
  payload: Record<string, unknown> | null
}

export interface JobTypeMetric {
  job_type: string
  count: number
  avg_duration_seconds: number | null
}

export interface MetricsSummary {
  total_events: number
  total_protocol_runs: number
  total_step_runs: number
  total_job_runs: number
  active_projects: number
  success_rate: number
  job_type_metrics: JobTypeMetric[]
  recent_events_count: number
}

// =============================================================================
// API Responses
// =============================================================================

export interface ActionResponse {
  message: string
  job?: {
    job_id: string
  }
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down"
  version?: string
}

// =============================================================================
// Branch
// =============================================================================

export interface Branch {
  name: string
  sha: string
  is_remote: boolean
}

// =============================================================================
// Agile / Sprint Board
// =============================================================================

export interface Sprint {
  id: number
  project_id: number
  name: string
  goal: string | null
  status: SprintStatus
  start_date: string | null
  end_date: string | null
  velocity_planned: number | null
  velocity_actual: number | null
  created_at: string
  updated_at: string
}

export interface SprintCreate {
  name: string
  goal?: string
  start_date?: string
  end_date?: string
  velocity_planned?: number
}

export interface AgileTask {
  id: number
  project_id: number
  sprint_id: number | null
  protocol_run_id: number | null
  step_run_id: number | null
  title: string
  description: string | null
  task_type: TaskType
  priority: TaskPriority
  board_status: TaskBoardStatus
  story_points: number | null
  assignee: string | null
  reporter: string | null
  labels: string[]
  acceptance_criteria: string[] | null
  blocked_by: number[] | null
  blocks: number[] | null
  due_date: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface AgileTaskCreate {
  title: string
  description?: string
  task_type?: TaskType
  priority?: TaskPriority
  board_status?: TaskBoardStatus
  story_points?: number
  assignee?: string
  sprint_id?: number
  labels?: string[]
  acceptance_criteria?: string[]
  due_date?: string
}

export interface AgileTaskUpdate {
  title?: string
  description?: string
  task_type?: TaskType
  priority?: TaskPriority
  board_status?: TaskBoardStatus
  story_points?: number
  assignee?: string
  sprint_id?: number
  labels?: string[]
  acceptance_criteria?: string[]
  blocked_by?: number[]
  due_date?: string
}

export interface SprintMetrics {
  sprint_id: number
  total_tasks: number
  completed_tasks: number
  total_points: number
  completed_points: number
  burndown: BurndownPoint[]
  velocity_trend: number[]
}

export interface SyncResult {
  sprint_id: number
  protocol_run_id: number
  tasks_synced: number
  task_ids: number[]
}

export interface BurndownPoint {
  date: string
  ideal: number
  actual: number
}

// =============================================================================
// Agent
// =============================================================================

export interface Agent {
  id: string
  name: string
  kind: string
  capabilities: string[]
  status: "available" | "busy" | "unavailable"
  default_model: string | null
  command_dir: string | null
  enabled?: boolean | null
  command?: string | null
  endpoint?: string | null
  sandbox?: string | null
  format?: string | null
  timeout_seconds?: number | null
  max_retries?: number | null
}

export interface AgentUpdate {
  name?: string | null
  kind?: string | null
  enabled?: boolean | null
  default_model?: string | null
  capabilities?: string[] | null
  command_dir?: string | null
  command?: string | null
  endpoint?: string | null
  sandbox?: string | null
  format?: string | null
  timeout_seconds?: number | null
  max_retries?: number | null
}

export interface AgentDefaults {
  code_gen?: string | null
  planning?: string | null
  exec?: string | null
  qa?: string | null
  discovery?: string | null
  prompts?: Record<string, string> | null
}

export interface AgentPromptTemplate {
  id: string
  name: string
  path: string
  kind?: string | null
  engine_id?: string | null
  model?: string | null
  tags?: string[] | null
  enabled?: boolean | null
  description?: string | null
  source?: "global" | "project" | null
}

export interface AgentPromptUpdate {
  name?: string | null
  path?: string | null
  kind?: string | null
  engine_id?: string | null
  model?: string | null
  tags?: string[] | null
  enabled?: boolean | null
  description?: string | null
}

export interface AgentProjectOverrides {
  inherit?: boolean
  agents?: Record<string, Record<string, unknown>>
  defaults?: Record<string, unknown>
  prompts?: Record<string, Record<string, unknown>>
  assignments?: Record<string, unknown>
}

export interface AgentHealth {
  agent_id: string
  available: boolean
  version?: string | null
  error?: string | null
  response_time_ms?: number | null
}

export interface AgentMetrics {
  agent_id: string
  active_steps: number
  completed_steps: number
  failed_steps: number
  total_steps: number
  last_activity_at?: string | null
}

// =============================================================================
// Specification
// =============================================================================

export interface Specification {
  id: number
  spec_run_id?: number | null
  path: string
  spec_path?: string | null
  plan_path?: string | null
  tasks_path?: string | null
  checklist_path?: string | null
  analysis_path?: string | null
  implement_path?: string | null
  title: string
  project_id: number
  project_name: string
  status: string
  created_at: string | null
  worktree_path?: string | null
  branch_name?: string | null
  base_branch?: string | null
  tasks_generated: boolean
  has_plan?: boolean
  has_tasks?: boolean
  protocol_id: number | null
  sprint_id: number | null
  sprint_name: string | null
  linked_tasks: number
  completed_tasks: number
  story_points: number
}
