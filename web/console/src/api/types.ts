export type Project = {
  id: number;
  name: string;
  git_url: string;
  local_path?: string | null;
  base_branch: string;
  ci_provider?: string | null;
  project_classification?: string | null;
  default_models?: Record<string, string> | null;
  created_at: string;
  updated_at: string;
  policy_pack_key?: string | null;
  policy_pack_version?: string | null;
  policy_effective_hash?: string | null;
  policy_enforcement_mode?: string | null;
};

export type ProjectCreate = {
  name: string;
  git_url: string;
  base_branch: string;
  ci_provider?: string | null;
  local_path?: string | null;
  project_classification?: string | null;
  default_models?: Record<string, string> | null;
  secrets?: Record<string, unknown> | null;
};

export type ProjectPolicyUpdate = {
  policy_pack_key?: string | null;
  policy_pack_version?: string | null;
  clear_policy_pack_version?: boolean;
  policy_overrides?: Record<string, unknown> | null;
  policy_repo_local_enabled?: boolean | null;
  policy_enforcement_mode?: string | null;
};

export type OnboardingSummary = {
  project_id: number;
  protocol_run_id?: number | null;
  status: string;
  workspace_path?: string | null;
  hint?: string | null;
  stages: Array<{ key: string; name: string; status: string; message?: string | null }>;
};

export type Clarification = {
  id: number;
  scope: string;
  project_id: number;
  protocol_run_id?: number | null;
  step_run_id?: number | null;
  key: string;
  question: string;
  recommended?: unknown;
  options?: unknown;
  applies_to?: string | null;
  blocking: boolean;
  answer?: unknown;
  status: string;
  answered_by?: string | null;
  answered_at?: string | null;
};

export type PolicyPack = {
  id: number;
  key: string;
  version: string;
  name: string;
  description?: string | null;
  status: string;
  pack: Record<string, unknown>;
};

export type ProtocolRunCreate = {
  protocol_name: string;
  status?: string;
  base_branch?: string;
  description?: string | null;
  worktree_path?: string | null;
  protocol_root?: string | null;
  template_config?: Record<string, unknown> | null;
  template_source?: Record<string, unknown> | null;
};

export type ProtocolRun = ProtocolRunCreate & {
  id: number;
  project_id: number;
  created_at: string;
  updated_at: string;
  status: string;
};

export type LogTailResponse = {
  run_id: string;
  offset: number;
  next_offset: number;
  eof: boolean;
  chunk: string;
};

export type CISummary = {
  protocol_run_id: number;
  provider?: string | null;
  pr_number?: number | null;
  pr_url?: string | null;
  sha?: string | null;
  status?: string | null;
  conclusion?: string | null;
  check_name?: string | null;
  last_event_type?: string | null;
  last_event_at?: string | null;
};

export type GitStatus = {
  protocol_run_id: number;
  repo_root?: string | null;
  worktree_path?: string | null;
  branch?: string | null;
  head_sha?: string | null;
  dirty: boolean;
  changed_files: string[];
};

