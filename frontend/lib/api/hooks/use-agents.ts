"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { Agent } from "../types"

// List Agents
export function useAgents() {
    return useQuery({
        queryKey: queryKeys.agents.list(),
        queryFn: () => apiClient.get<Agent[]>("/agents"),
    })
}

// Get Agent by ID
export function useAgent(id: string | undefined) {
    return useQuery({
        queryKey: queryKeys.agents.detail(id!),
        queryFn: () => apiClient.get<Agent>(`/agents/${id}`),
        enabled: !!id,
    })
}
