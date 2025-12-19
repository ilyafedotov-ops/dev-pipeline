"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { Specification } from "../types"

// =============================================================================
// Types
// =============================================================================

export interface SpecificationFilters {
    project_id?: number
    sprint_id?: number
    status?: "draft" | "in-progress" | "completed"
    date_from?: string
    date_to?: string
    has_plan?: boolean
    has_tasks?: boolean
    search?: string
    [key: string]: unknown
}

export interface SpecificationsListResponse {
    items: Specification[]
    total: number
    filters_applied: Record<string, unknown>
}

export interface SpecificationContent {
    id: number
    path: string
    title: string
    spec_content: string | null
    plan_content: string | null
    tasks_content: string | null
    checklist_content: string | null
}

export interface LinkSprintRequest {
    sprint_id: number | null
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * List specifications with comprehensive filtering
 */
export function useSpecifications(filters?: SpecificationFilters) {
    const params = new URLSearchParams()

    if (filters?.project_id) params.append("project_id", filters.project_id.toString())
    if (filters?.sprint_id) params.append("sprint_id", filters.sprint_id.toString())
    if (filters?.status) params.append("status", filters.status)
    if (filters?.date_from) params.append("date_from", filters.date_from)
    if (filters?.date_to) params.append("date_to", filters.date_to)
    if (filters?.has_plan !== undefined) params.append("has_plan", filters.has_plan.toString())
    if (filters?.has_tasks !== undefined) params.append("has_tasks", filters.has_tasks.toString())
    if (filters?.search) params.append("search", filters.search)

    const queryString = params.toString()
    const url = `/specifications${queryString ? `?${queryString}` : ""}`

    return useQuery({
        queryKey: queryKeys.specifications.list(filters?.project_id, filters),
        queryFn: async () => {
            const response = await apiClient.get<SpecificationsListResponse>(url)
            // Return items array for backward compatibility, but expose full response
            return response.items
        },
    })
}

/**
 * List specifications with full response including total and filters
 */
export function useSpecificationsWithMeta(filters?: SpecificationFilters) {
    const params = new URLSearchParams()

    if (filters?.project_id) params.append("project_id", filters.project_id.toString())
    if (filters?.sprint_id) params.append("sprint_id", filters.sprint_id.toString())
    if (filters?.status) params.append("status", filters.status)
    if (filters?.date_from) params.append("date_from", filters.date_from)
    if (filters?.date_to) params.append("date_to", filters.date_to)
    if (filters?.has_plan !== undefined) params.append("has_plan", filters.has_plan.toString())
    if (filters?.has_tasks !== undefined) params.append("has_tasks", filters.has_tasks.toString())
    if (filters?.search) params.append("search", filters.search)

    const queryString = params.toString()
    const url = `/specifications${queryString ? `?${queryString}` : ""}`

    return useQuery({
        queryKey: ["specifications", "withMeta", filters],
        queryFn: () => apiClient.get<SpecificationsListResponse>(url),
    })
}

/**
 * Get a single specification by ID
 */
export function useSpecification(id: number | undefined) {
    return useQuery({
        queryKey: queryKeys.specifications.detail(id!),
        queryFn: () => apiClient.get<Specification>(`/specifications/${id}`),
        enabled: !!id,
    })
}

/**
 * Get specification content (spec.md, plan.md, tasks.md)
 */
export function useSpecificationContent(id: number | undefined) {
    return useQuery({
        queryKey: ["specifications", id, "content"],
        queryFn: () => apiClient.get<SpecificationContent>(`/specifications/${id}/content`),
        enabled: !!id,
    })
}

/**
 * Link/unlink specification to sprint
 */
export function useLinkSpecificationToSprint() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ specId, sprintId }: { specId: number; sprintId: number | null }) =>
            apiClient.post(`/specifications/${specId}/link-sprint`, { sprint_id: sprintId }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.specifications.all })
        },
    })
}
