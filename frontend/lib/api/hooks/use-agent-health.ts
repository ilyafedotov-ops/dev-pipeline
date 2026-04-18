"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";
import type { AgentHealth, AgentMetrics } from "../types";

// =============================================================================
// Types
// =============================================================================

/** Response from GET /api/v1/agents/{agentId}/health */
export interface AgentHealthCheckResponse {
  available: boolean;
  version: string;
  responseTimeMs: number;
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * List health status for all agents (optionally filtered by project).
 * GET /api/v1/agents/health
 */
export function useAgentHealth(projectId?: number) {
  const suffix = projectId ? `?project_id=${projectId}` : "";
  return useQuery({
    queryKey: queryKeys.agents.health(projectId),
    queryFn: () => apiClient.get<AgentHealth[]>(`/agents/health${suffix}`),
  });
}

/**
 * Check health for a specific agent by ID.
 * GET /api/v1/agents/{agentId}/health
 */
export function useAgentHealthCheck(agentId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.agents.healthCheck(agentId as string),
    queryFn: () =>
      apiClient.get<AgentHealthCheckResponse>(`/agents/${agentId}/health`),
    enabled: !!agentId,
    refetchInterval: 30_000, // Refresh health every 30s
  });
}

export function useAgentMetrics(projectId?: number) {
  const suffix = projectId ? `?project_id=${projectId}` : "";
  return useQuery({
    queryKey: queryKeys.agents.metrics(projectId),
    queryFn: () => apiClient.get<AgentMetrics[]>(`/agents/metrics${suffix}`),
  });
}
