"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { QueueStats, QueueJob, Event, EventFilters, HealthResponse } from "../types"

// Health Check
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiClient.get<HealthResponse>("/health"),
    refetchInterval: 30000, // Check every 30s
  })
}

// Queue Stats
export function useQueueStats() {
  return useQuery({
    queryKey: queryKeys.ops.queueStats,
    queryFn: () => apiClient.get<QueueStats[]>("/queues"),
    refetchInterval: 10000,
  })
}

// Queue Jobs
export function useQueueJobs(status?: string) {
  return useQuery({
    queryKey: queryKeys.ops.queueJobs(status),
    queryFn: () => apiClient.get<QueueJob[]>(`/queues/jobs${status ? `?status=${status}` : ""}`),
    refetchInterval: 5000,
  })
}

// Recent Events
export function useRecentEvents(filters: EventFilters = {}) {
  return useQuery({
    queryKey: queryKeys.ops.recentEvents(filters),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.project_id) params.set("project_id", String(filters.project_id))
      if (filters.protocol_run_id) params.set("protocol_id", String(filters.protocol_run_id))
      if (filters.kind) params.set("kind", filters.kind)
      if (filters.spec_hash) params.set("spec_hash", filters.spec_hash)
      if (filters.limit) params.set("limit", String(filters.limit))
      const queryString = params.toString()
      const response = await apiClient.get<{ events: Event[] }>(`/events/recent${queryString ? `?${queryString}` : ""}`)
      return response.events
    },
    refetchInterval: 10000,
  })
}
