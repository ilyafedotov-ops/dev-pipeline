"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { Specification } from "../types"

// List Specifications
export function useSpecifications(projectId?: number) {
    return useQuery({
        queryKey: queryKeys.specifications.list(projectId),
        queryFn: () => {
            const params = projectId ? `?project_id=${projectId}` : ""
            return apiClient.get<Specification[]>(`/specifications${params}`)
        },
    })
}

// Get Specification by ID
export function useSpecification(id: number | undefined) {
    return useQuery({
        queryKey: queryKeys.specifications.detail(id!),
        queryFn: () => apiClient.get<Specification>(`/specifications/${id}`),
        enabled: !!id,
    })
}
