import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";
import {
  CLIExecution,
  CLIExecutionFilters,
  CLIExecutionListResponse,
  LogEntry,
} from "../types/cli-executions";

// Query Keys
export const cliExecutionKeys = {
  all: ["cli-executions"] as const,
  list: (filters: CLIExecutionFilters) => [...cliExecutionKeys.all, "list", filters] as const,
  active: () => [...cliExecutionKeys.all, "active"] as const,
  detail: (executionId: string) => [...cliExecutionKeys.all, "detail", executionId] as const,
  logs: (executionId: string) => [...cliExecutionKeys.all, "logs", executionId] as const,
};

// Hooks

export function useCLIExecutions(filters: CLIExecutionFilters = {}) {
  return useQuery({
    queryKey: cliExecutionKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.execution_type) params.set("execution_type", filters.execution_type);
      if (filters.project_id) params.set("project_id", String(filters.project_id));
      if (filters.status) params.set("status", filters.status);
      if (filters.limit) params.set("limit", String(filters.limit));

      const queryString = params.toString();
      return apiClient.get<CLIExecutionListResponse>(
        `/cli-executions${queryString ? `?${queryString}` : ""}`
      );
    },
    refetchInterval: 5000, // Poll every 5 seconds
  });
}

export function useActiveCLIExecutions(limit: number = 50) {
  return useQuery({
    queryKey: cliExecutionKeys.active(),
    queryFn: () => apiClient.get<CLIExecutionListResponse>(`/cli-executions/active?limit=${limit}`),
    refetchInterval: 2000, // Poll active executions more frequently
  });
}

export function useCLIExecution(executionId: string | undefined) {
  return useQuery({
    queryKey: cliExecutionKeys.detail(executionId as string),
    queryFn: () => apiClient.get<CLIExecution>(`/cli-executions/${executionId}`),
    enabled: !!executionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["running", "pending"].includes(status) ? 2000 : false;
    },
  });
}

export function useCLIExecutionLogs(executionId: string | undefined) {
  return useQuery({
    queryKey: cliExecutionKeys.logs(executionId as string),
    queryFn: () => apiClient.get<{ logs: LogEntry[] }>(`/cli-executions/${executionId}/logs`),
    enabled: !!executionId,
  });
}

// Custom hook for streaming logs via SSE
export function useCLIExecutionLogStream(executionId: string | undefined) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!executionId) return;

    setLogs([]); // Clear logs when ID changes
    setStatus("connecting");

    // Construct the SSE URL.
    // We need to use the full URL including the API base if it's external, or relative if proxied.
    // apiClient.baseUrl might be helpful here if accessible, otherwise assume relative to /api/v1 or similar
    // For this setup, we know it's /cli-executions/... handled by Next.js rewrites or Nginx

    const config = apiClient.getConfig();
    const url = `${config.baseUrl}/cli-executions/${executionId}/logs/stream${config.token ? `?token=${config.token}` : ""}`;

    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
      setIsConnected(true);
      setStatus("connected");
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs((prev) => [...prev, data]);
      } catch (err) {
        console.error("Failed to parse log entry:", err);
      }
    };

    // Custom events
    eventSource.addEventListener("status", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status);
        // Invalidate the detail query to refresh status in other components
        queryClient.invalidateQueries({ queryKey: cliExecutionKeys.detail(executionId) });
      } catch (err) {
        console.error("Failed to parse status event:", err);
      }
    });

    eventSource.addEventListener("complete", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status);
        eventSource.close();
        setIsConnected(false);
        queryClient.invalidateQueries({ queryKey: cliExecutionKeys.detail(executionId) });
      } catch (err) {
        console.error("Failed to parse complete event:", err);
      }
    });

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
      if (eventSource.readyState === EventSource.CLOSED) {
        setIsConnected(false);
        setStatus("disconnected");
      }
    };

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [executionId, queryClient]);

  return { logs, status, isConnected };
}

// Response type for the cancel endpoint
export interface CancelExecutionResponse {
  execution_id: string;
  status: string;
  message: string;
  pid: number | null;
  termination_attempted: boolean;
  termination_result: string;
  termination_error?: string;
}

/**
 * Cancel a running CLI execution
 */
export function useCancelCLIExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (executionId: string) =>
      apiClient.post<CancelExecutionResponse>(`/cli-executions/${executionId}/cancel`),
    onSuccess: (_, executionId) => {
      // Invalidate the specific execution detail
      queryClient.invalidateQueries({ queryKey: cliExecutionKeys.detail(executionId) });
      // Invalidate the lists to reflect the status change
      queryClient.invalidateQueries({ queryKey: cliExecutionKeys.all });
    },
  });
}
