"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";

export interface WindmillJob {
  id: string;
  status: string;
  script_path?: string;
  job_kind?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  completed_at?: string;
  duration_ms?: number;
  result?: unknown;
  error?: string;
  [key: string]: unknown;
}

export interface WindmillJobLog {
  content: string;
  [key: string]: unknown;
}

export interface WindmillJobsParams {
  per_page?: number;
  page?: number;
  job_kinds?: string;
  script_path_exact?: string;
}

export function useWindmillJobs(params?: WindmillJobsParams) {
  return useQuery({
    queryKey: ["windmill", "jobs", params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params?.per_page) searchParams.set("per_page", String(params.per_page));
      if (params?.page) searchParams.set("page", String(params.page));
      if (params?.job_kinds) searchParams.set("job_kinds", params.job_kinds);
      if (params?.script_path_exact)
        searchParams.set("script_path_exact", params.script_path_exact);
      const qs = searchParams.toString();
      return apiClient.get<WindmillJob[]>(`/jobs${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useWindmillJob(jobId: string) {
  return useQuery({
    queryKey: ["windmill", "jobs", jobId],
    queryFn: () => apiClient.get<WindmillJob>(`/jobs/${encodeURIComponent(jobId)}`),
    enabled: !!jobId,
  });
}

export function useWindmillJobLogs(jobId: string) {
  return useQuery({
    queryKey: ["windmill", "jobs", jobId, "logs"],
    queryFn: () => apiClient.get<WindmillJobLog>(`/jobs/${encodeURIComponent(jobId)}/logs`),
    enabled: !!jobId,
  });
}
