"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"

// =============================================================================
// Types
// =============================================================================

export interface SpecKitStatus {
    initialized: boolean
    constitution_hash: string | null
    constitution_version: string | null
    spec_count: number
    specs: SpecListItem[]
}

export interface SpecListItem {
    name: string
    path: string
    spec_path?: string | null
    plan_path?: string | null
    tasks_path?: string | null
    has_spec: boolean
    has_plan: boolean
    has_tasks: boolean
}

export interface SpecKitInitRequest {
    project_id: number
    constitution_content?: string
}

export interface SpecKitInitResponse {
    success: boolean
    path: string | null
    constitution_hash: string | null
    error: string | null
    warnings: string[]
}

export interface SpecifyRequest {
    project_id: number
    description: string
    feature_name?: string
}

export interface SpecifyResponse {
    success: boolean
    spec_path: string | null
    spec_number: number | null
    feature_name: string | null
    error: string | null
}

export interface PlanRequest {
    project_id: number
    spec_path: string
}

export interface PlanResponse {
    success: boolean
    plan_path: string | null
    data_model_path: string | null
    contracts_path: string | null
    error: string | null
}

export interface TasksRequest {
    project_id: number
    plan_path: string
}

export interface TasksResponse {
    success: boolean
    tasks_path: string | null
    task_count: number
    parallelizable_count: number
    error: string | null
}

export interface ClarificationEntry {
    question: string
    answer: string
}

export interface ClarifyRequest {
    project_id: number
    spec_path: string
    entries?: ClarificationEntry[]
    notes?: string
}

export interface ClarifyResponse {
    success: boolean
    spec_path: string | null
    clarifications_added: number
    error: string | null
}

export interface ChecklistRequest {
    project_id: number
    spec_path: string
}

export interface ChecklistResponse {
    success: boolean
    checklist_path: string | null
    item_count: number
    error: string | null
}

export interface AnalyzeRequest {
    project_id: number
    spec_path: string
    plan_path?: string
    tasks_path?: string
}

export interface AnalyzeResponse {
    success: boolean
    report_path: string | null
    error: string | null
}

export interface ImplementRequest {
    project_id: number
    spec_path: string
}

export interface ImplementResponse {
    success: boolean
    run_path: string | null
    metadata_path: string | null
    error: string | null
}

export interface ConstitutionResponse {
    content: string
}

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
    })
}

/**
 * Get constitution content for a project
 */
export function useConstitution(projectId: number | undefined) {
    return useQuery({
        queryKey: ["speckit", "constitution", projectId],
        queryFn: () => apiClient.get<ConstitutionResponse>(`/speckit/constitution/${projectId}`),
        enabled: !!projectId,
    })
}

/**
 * Initialize SpecKit for a project
 */
export function useInitSpecKit() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: SpecKitInitRequest) =>
            apiClient.post<SpecKitInitResponse>("/speckit/init", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "constitution", variables.project_id] })
        },
    })
}

/**
 * Save/update constitution for a project
 */
export function useSaveConstitution() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ projectId, content }: { projectId: number; content: string }) =>
            apiClient.put<SpecKitInitResponse>(`/speckit/constitution/${projectId}`, { content }),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "constitution", variables.projectId] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.projectId] })
        },
    })
}

/**
 * Generate a feature specification from description
 */
export function useGenerateSpec() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: SpecifyRequest) =>
            apiClient.post<SpecifyResponse>("/speckit/specify", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Generate implementation plan from a spec
 */
export function useGeneratePlan() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: PlanRequest) =>
            apiClient.post<PlanResponse>("/speckit/plan", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Generate tasks from an implementation plan
 */
export function useGenerateTasks() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: TasksRequest) =>
            apiClient.post<TasksResponse>("/speckit/tasks", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Append clarifications to a spec
 */
export function useClarifySpec() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: ClarifyRequest) =>
            apiClient.post<ClarifyResponse>("/speckit/clarify", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Generate a checklist for a spec
 */
export function useGenerateChecklist() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: ChecklistRequest) =>
            apiClient.post<ChecklistResponse>("/speckit/checklist", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Run analysis for a spec
 */
export function useAnalyzeSpec() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: AnalyzeRequest) =>
            apiClient.post<AnalyzeResponse>("/speckit/analyze", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * Initialize an implementation run for a spec
 */
export function useRunImplement() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: ImplementRequest) =>
            apiClient.post<ImplementResponse>("/speckit/implement", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}

/**
 * List specs for a project (from SpecKit)
 */
export function useProjectSpecs(projectId: number | undefined) {
    return useQuery({
        queryKey: ["speckit", "specs", projectId],
        queryFn: () => apiClient.get<SpecListItem[]>(`/speckit/specs/${projectId}`),
        enabled: !!projectId,
    })
}

// =============================================================================
// Workflow Orchestration
// =============================================================================

export interface WorkflowRequest {
    project_id: number
    description: string
    feature_name?: string
    stop_after?: "spec" | "plan" | null
}

export interface WorkflowStepResult {
    step: string
    success: boolean
    path: string | null
    error: string | null
    skipped: boolean
}

export interface WorkflowResponse {
    success: boolean
    spec_path: string | null
    plan_path: string | null
    tasks_path: string | null
    task_count: number
    parallelizable_count: number
    steps: WorkflowStepResult[]
    stopped_after: string | null
    error: string | null
}

/**
 * Run the full SpecKit workflow: spec → plan → tasks
 * Use stop_after to run partial pipelines
 */
export function useRunWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: WorkflowRequest) =>
            apiClient.post<WorkflowResponse>("/speckit/workflow", request),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["speckit", "status", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: ["speckit", "specs", variables.project_id] })
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}
