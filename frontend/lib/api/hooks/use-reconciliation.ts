"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/lib/api/client";

export interface ReconciliationStatus {
  last_run?: string;
  last_status?: string;
  last_report?: Record<string, unknown> | string;
  total_reconciled?: number;
  protocols?: Record<string, unknown> | string;
  steps?: Record<string, unknown> | string;
  [key: string]: unknown;
}

export function useReconciliationStatus() {
  return useQuery({
    queryKey: ["reconciliation", "status"],
    queryFn: () => apiClient.get<ReconciliationStatus>("/reconciliation/status"),
  });
}

export function useReconcileProtocol(protocolRunId: string, dryRun = false) {
  return useQuery({
    queryKey: ["reconciliation", "protocols", protocolRunId, dryRun],
    queryFn: () => {
      const params = new URLSearchParams();
      if (dryRun) params.set("dry_run", "true");
      const qs = params.toString();
      return apiClient.get(
        `/reconciliation/protocols/${encodeURIComponent(protocolRunId)}${qs ? `?${qs}` : ""}`
      );
    },
    enabled: !!protocolRunId,
  });
}

export function useReconcileStep(stepRunId: string, dryRun = false) {
  return useQuery({
    queryKey: ["reconciliation", "steps", stepRunId, dryRun],
    queryFn: () => {
      const params = new URLSearchParams();
      if (dryRun) params.set("dry_run", "true");
      const qs = params.toString();
      return apiClient.get(
        `/reconciliation/steps/${encodeURIComponent(stepRunId)}${qs ? `?${qs}` : ""}`
      );
    },
    enabled: !!stepRunId,
  });
}

export function useRunReconciliation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      protocol_run_id?: string;
      dry_run?: boolean;
      background?: boolean;
    }) => apiClient.post("/reconciliation/run", params),
    onSuccess: () => {
      toast.success("Reconciliation triggered");
      queryClient.invalidateQueries({ queryKey: ["reconciliation"] });
    },
  });
}
