// DevGodzilla TypeScript Types
// Based on API-ARCHITECTURE.md schemas

// ============ Core Types ============

export interface Project {
  id: number;
  name: string;
  description?: string;
  git_url?: string;
  base_branch: string;
  local_path?: string;
  status?: 'active' | 'archived';
  constitution_version?: string;
  constitution_hash?: string;
  project_classification?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Protocol {
  id: number;
  protocol_name: string;
  project_id: number;
  status: ProtocolStatus;
  summary?: string;
  base_branch?: string;
  created_at: string;
  updated_at?: string;
}

export type ProtocolStatus = 
  | 'pending'
  | 'planning'
  | 'planned'
  | 'running'
  | 'needs_qa'
  | 'paused'
  | 'blocked'
  | 'failed'
  | 'completed'
  | 'cancelled';

export interface Step {
  id: number;
  step_name: string;
  step_type: string;
  step_index: number;
  status: StepStatus;
  assigned_agent?: string;
  summary?: string;
  protocol_run_id: number;
  depends_on?: string[];
}

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'blocked';

export interface Clarification {
  id: number;
  key: string;
  question: string;
  status: 'open' | 'answered';
  protocol_run_id: number;
  step_id?: string;
  options?: string[];
  recommended?: { value: string; reason: string };
  answer?: string;
  blocking: boolean;
  created_at: string;
}

// ============ SpecKit Types ============

export interface UserStory {
  id: string; // US1, US2, etc.
  title: string;
  priority: 'P1' | 'P2' | 'P3';
  description: string;
}

export interface SpecifyRequest {
  description: string;
  branch_name: string;
  clarifications?: Record<string, string>;
}

export interface SpecifyResponse {
  spec_id: string;
  feature_name: string;
  branch_name: string;
  spec_path: string;
  user_stories: UserStory[];
  created_at: string;
}

export interface Task {
  id: string; // T001, T002, etc.
  description: string;
  parallel: boolean;
  story?: string;
  depends_on: string[];
  status?: StepStatus;
}

export interface Phase {
  phase: number;
  name: string;
  story_id?: string;
  mvp: boolean;
  tasks: Task[];
}

export interface DAGDefinition {
  nodes: string[];
  edges: [string, string][];
}

export interface TasksResponse {
  tasks_id: string;
  tasks_path: string;
  phases: Phase[];
  dag: DAGDefinition;
  parallel_groups: Record<string, string[]>;
}

// ============ Agent Types ============

export interface Agent {
  id: string;
  name: string;
  kind: 'cli' | 'ide';
  status: 'available' | 'unavailable' | 'error';
  default_model?: string;
  command_dir?: string;
  capabilities: string[];
}

export interface AgentConfig {
  agent_id: string;
  default_model?: string;
  sandbox?: 'workspace-read' | 'workspace-write' | 'full-access';
  timeout_seconds?: number;
  max_retries?: number;
  environment?: Record<string, string>;
}

export interface AgentAssignRequest {
  agent_id: string;
  config_override?: Partial<AgentConfig>;
}

// ============ Quality Types ============

export interface GateFinding {
  code: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
  step_id?: string;
  suggested_fix?: string;
}

export interface GateResult {
  article: string;
  name: string;
  status: 'passed' | 'warning' | 'failed' | 'skipped';
  findings: GateFinding[];
}

export interface ChecklistItem {
  id: string;
  description: string;
  passed: boolean;
  required: boolean;
}

export interface ChecklistResult {
  passed: number;
  total: number;
  items: ChecklistItem[];
}

export interface QualitySummary {
  protocol_run_id: number;
  constitution_version: string;
  score: number;
  gates: GateResult[];
  checklist: ChecklistResult;
  overall_status: 'passed' | 'warning' | 'failed';
  blocking_issues: number;
  warnings: number;
}

// ============ Feedback Types ============

export type FeedbackErrorType = 'specification_error' | 'task_graph_error' | 'execution_error';
export type FeedbackAction = 'clarify' | 're_plan' | 're_specify' | 'retry';

export interface FeedbackRequest {
  error_type: FeedbackErrorType;
  step_id?: string;
  action: FeedbackAction;
  context: Record<string, unknown>;
}

export interface FeedbackResponse {
  feedback_id: string;
  action_taken: string;
  clarification?: Clarification;
  protocol_status: ProtocolStatus;
}

export interface FeedbackEvent {
  id: string;
  error_type?: FeedbackErrorType;
  action_taken: string;
  clarification?: Clarification;
  created_at: string;
  resolved: boolean;
}

// ============ Flow/Job Types ============

export interface WindmillFlow {
  id: string;
  path: string;
  summary: string;
  created_at: string;
}

export interface Job {
  id: string;
  flow_path?: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface Run {
  id: number;
  protocol_run_id: number;
  step_id: number;
  status: StepStatus;
  logs?: string;
  artifacts?: Artifact[];
  started_at: string;
  completed_at?: string;
}

export interface Artifact {
  id: string;
  name: string;
  path: string;
  size: number;
  created_at: string;
}

// ============ System Types ============

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  components: Record<string, 'ok' | 'error'>;
  agents: Record<string, 'available' | 'unavailable' | 'error'>;
}

export interface Event {
  id: string;
  event_type: string;
  message: string;
  protocol_id?: number;
  step_id?: number;
  created_at: string;
}

// ============ Stats Types ============

export interface DashboardStats {
  total_projects: number;
  active_projects: number;
  archived_projects: number;
  total_protocols: number;
  running_protocols: number;
  completed_today: number;
  pending_clarifications: number;
}

// ============ API Response Wrappers ============

export interface ApiError {
  code: string;
  message: string;
  details?: { field: string; message: string }[];
}

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  request_id?: string;
}

// ============ Navigation Types ============

export type ViewName =
  | 'dashboard'
  | 'projects'
  | 'project'
  | 'create-project'
  | 'protocols'
  | 'protocol'
  | 'clarifications'
  | 'agents'
  | 'agent'
  | 'quality'
  | 'speckit'
  | 'settings';
