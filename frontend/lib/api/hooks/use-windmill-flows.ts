"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface WindmillFlow {
  path: string;
  name: string;
  summary: string;
  schema?: Record<string, unknown>;
  value?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface WindmillFlowRun {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string;
  success?: boolean;
  [key: string]: unknown;
}

export function useWindmillFlows(prefix?: string) {
  return useQuery({
    queryKey: ["windmill", "flows", prefix],
    queryFn: () => {
      const params = new URLSearchParams();
      if (prefix) params.set("prefix", prefix);
      const qs = params.toString();
      return apiClient.get<WindmillFlow[]>(`/flows${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useWindmillFlow(flowPath: string) {
  return useQuery({
    queryKey: ["windmill", "flows", flowPath],
    queryFn: () => apiClient.get<WindmillFlow>(`/flows/${encodeURIComponent(flowPath)}`),
    enabled: !!flowPath,
  });
}

export function useWindmillFlowRuns(flowPath: string, page = 1, perPage = 20) {
  return useQuery({
    queryKey: ["windmill", "flows", flowPath, "runs", page, perPage],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", String(perPage));
      return apiClient.get<WindmillFlowRun[]>(
        `/flows/${encodeURIComponent(flowPath)}/runs?${params.toString()}`
      );
    },
    enabled: !!flowPath,
  });
}
