"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";

// =============================================================================
// Types
// =============================================================================

export interface SpecKitStatus {
  initialized: boolean;
  constitution_hash: string | null;
  constitution_version: string | null;
  spec_count: number;
  specs: SpecListItem[];
}

export interface SpecListItem {
  id?: number;
  name: string;
  path: string;
  spec_path?: string | null;
  plan_path?: string | null;
  tasks_path?: string | null;
  checklist_path?: string | null;
  analysis_path?: string | null;
  implement_path?: string | null;
  has_spec: boolean;
  has_plan: boolean;
  has_tasks: boolean;
  status?: string | null;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  branch_name?: string | null;
  base_branch?: string | null;
  spec_number?: number | null;
  feature_name?: string | null;
  error_message?: string | null;
}

export interface SpecKitInitRequest {
  project_id: number;
  constitution_content?: string;
}

export interface SpecKitInitResponse {
  success: boolean;
  path: string | null;
  constitution_hash: string | null;
  error: string | null;
  warnings: string[];
}

export interface SpecifyRequest {
  project_id: number;
  description: string;
  feature_name?: string;
  base_branch?: string;
}

export interface SpecifyResponse {
  success: boolean;
  spec_path: string | null;
  spec_number: number | null;
  feature_name: string | null;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  branch_name?: string | null;
  base_branch?: string | null;
  spec_root?: string | null;
  error: string | null;
}

export interface PlanRequest {
  project_id: number;
  spec_path: string;
  spec_run_id?: number;
  context?: string;
}

export interface PlanResponse {
  success: boolean;
  plan_path: string | null;
  data_model_path: string | null;
  contracts_path: string | null;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface TasksRequest {
  project_id: number;
  plan_path: string;
  spec_run_id?: number;
}

export interface TasksResponse {
  success: boolean;
  tasks_path: string | null;
  task_count: number;
  parallelizable_count: number;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface ClarificationEntry {
  question: string;
  answer: string;
}

export interface ClarifyRequest {
  project_id: number;
  spec_path: string;
  entries?: ClarificationEntry[];
  notes?: string;
  spec_run_id?: number;
}

export interface ClarifyResponse {
  success: boolean;
  spec_path: string | null;
  clarifications_added: number;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface ChecklistRequest {
  project_id: number;
  spec_path: string;
  spec_run_id?: number;
}

export interface ChecklistResponse {
  success: boolean;
  checklist_path: string | null;
  item_count: number;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface AnalyzeRequest {
  project_id: number;
  spec_path: string;
  plan_path?: string;
  tasks_path?: string;
  spec_run_id?: number;
}

export interface AnalyzeResponse {
  success: boolean;
  report_path: string | null;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface ImplementRequest {
  project_id: number;
  spec_path: string;
  spec_run_id?: number;
}

export interface ImplementResponse {
  success: boolean;
  run_path: string | null;
  metadata_path: string | null;
  protocol_id?: number | null;
  protocol_root?: string | null;
  step_count?: number;
  warnings?: string[];
  spec_run_id?: number | null;
  worktree_path?: string | null;
  error: string | null;
}

export interface SpecRunCleanupRequest {
  delete_remote_branch?: boolean;
}

export interface SpecRunCleanupResponse {
  success: boolean;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  deleted_remote_branch: boolean;
  error?: string | null;
}

// Note: ConstitutionResponse, useConstitution, and useSaveConstitution are
// exported from ./use-constitution.ts to avoid duplicate exports.

// =============================================================================
// Hooks
// =============================================================================

/**
 * Get SpecKit initialization status for a project
 */
export function useSpecKitStatus(projectId: number | undefined) {
  return useQuery({
    queryKey: ["speckit", "status", projectId],
    queryFn: () => apiClient.get<SpecKitStatus>(`/speckit/status/${projectId}`),
    enabled: !!projectId,
  });
}

/**
 * Initialize SpecKit for a project
 */
export function useInitSpecKit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, constitution_content }: SpecKitInitRequest) =>
      apiClient.post<SpecKitInitResponse>(
        `/projects/${project_id}/speckit/init`,
        constitution_content ? { content: constitution_content } : undefined
      ),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({
        queryKey: ["speckit", "constitution", variables.project_id],
      });
    },
  });
}

/**
 * Generate a feature specification from description
 */
export function useGenerateSpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: SpecifyRequest) =>
      apiClient.post<SpecifyResponse>(`/projects/${project_id}/speckit/specify`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Generate implementation plan from a spec
 */
export function useGeneratePlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: PlanRequest) =>
      apiClient.post<PlanResponse>(`/projects/${project_id}/speckit/plan`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Generate tasks from an implementation plan
 */
export function useGenerateTasks() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: TasksRequest) =>
      apiClient.post<TasksResponse>(`/projects/${project_id}/speckit/tasks`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Append clarifications to a spec
 */
export function useClarifySpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: ClarifyRequest) =>
      apiClient.post<ClarifyResponse>(`/projects/${project_id}/speckit/clarify`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Generate a checklist for a spec
 */
export function useGenerateChecklist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: ChecklistRequest) =>
      apiClient.post<ChecklistResponse>(`/projects/${project_id}/speckit/checklist`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Run analysis for a spec
 */
export function useAnalyzeSpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: AnalyzeRequest) =>
      apiClient.post<AnalyzeResponse>(`/projects/${project_id}/speckit/analyze`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Initialize an implementation run for a spec
 */
export function useRunImplement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ project_id, ...request }: ImplementRequest) =>
      apiClient.post<ImplementResponse>(`/projects/${project_id}/speckit/implement`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * List specs for a project (from SpecKit)
 */
export function useProjectSpecs(projectId: number | undefined) {
  return useQuery({
    queryKey: ["speckit", "specs", projectId],
    queryFn: () => apiClient.get<SpecListItem[]>(`/speckit/specs/${projectId}`),
    enabled: !!projectId,
  });
}

// =============================================================================
// Workflow Orchestration
// =============================================================================

export interface WorkflowRequest {
  project_id: number;
  description: string;
  feature_name?: string;
  base_branch?: string;
  stop_after?: "spec" | "plan" | null;
}

export interface WorkflowStepResult {
  step: string;
  success: boolean;
  path: string | null;
  error: string | null;
  skipped: boolean;
}

export interface WorkflowResponse {
  success: boolean;
  spec_path: string | null;
  plan_path: string | null;
  tasks_path: string | null;
  task_count: number;
  parallelizable_count: number;
  spec_run_id?: number | null;
  worktree_path?: string | null;
  steps: WorkflowStepResult[];
  stopped_after: string | null;
  error: string | null;
}

/**
 * Cleanup a SpecRun worktree and artifacts
 */
export function useCleanupSpecRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ specRunId, payload }: { specRunId: number; payload?: SpecRunCleanupRequest }) =>
      apiClient.post<SpecRunCleanupResponse>(
        `/speckit/spec-runs/${specRunId}/cleanup`,
        payload ?? {}
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status"] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

// Response type for the stop spec run endpoint
export interface SpecRunStopResponse {
  success: boolean;
  spec_run_id?: number | null;
  previous_status?: string | null;
  status?: string | null;
  error?: string | null;
}

/**
 * Stop a running spec run
 */
export function useStopSpecRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (specRunId: number) =>
      apiClient.post<SpecRunStopResponse>(`/speckit/spec-runs/${specRunId}/stop`),
    onSuccess: () => {
      // Invalidate all speckit-related queries
      queryClient.invalidateQueries({ queryKey: ["speckit", "status"] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

/**
 * Run the full SpecKit workflow: spec → plan → tasks
 * Use stop_after to run partial pipelines
 */
export function useRunWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: WorkflowRequest) =>
      apiClient.post<WorkflowResponse>("/speckit/workflow", request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] });
      queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all });
    },
  });
}

// =============================================================================
// AI-powered Clarification
// =============================================================================

export interface ClarificationItem {
  id: number;
  scope?: string | null;
  project_id?: number | null;
  protocol_run_id?: number | null;
  step_run_id?: number | null;
  key?: string | null;
  question: string;
  status: string;
  options?: string[] | null;
  recommended?: Record<string, unknown> | null;
  applies_to?: string | null;
  blocking?: boolean | null;
  answer?: Record<string, unknown> | null;
  created_at?: string | null;
  answered_at?: string | null;
  answered_by?: string | null;
}

export interface DetectAmbiguitiesRequest {
  spec_path: string;
  spec_run_id?: number | null;
  context?: string | null;
}

export interface DetectAmbiguitiesResponse {
  success: boolean;
  clarifications: ClarificationItem[];
  error?: string | null;
}

/**
 * Delete a specification (spec run + worktree files)
 */
export function useDeleteSpecRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ project_id, spec_run_id }: { project_id: number; spec_run_id: number }) =>
      apiClient.delete<SpecRunCleanupResponse>(`/projects/${project_id}/speckit/specs/${spec_run_id}`),
    onSuccess: (_data, { project_id }) => {
      queryClient.invalidateQueries({ queryKey: ["speckit-status", project_id] });
      queryClient.invalidateQueries({ queryKey: ["project-specs", project_id] });
    },
  });
}

/**
 * Detect ambiguities in a spec using AI-powered analysis
 */
export function useDetectAmbiguities() {
  return useMutation({
    mutationFn: ({ project_id, ...request }: { project_id: number } & DetectAmbiguitiesRequest) =>
      apiClient.post<DetectAmbiguitiesResponse>(
        `/projects/${project_id}/speckit/detect-ambiguities`,
        request
      ),
  });
}
