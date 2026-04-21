"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { adaptProtocol, adaptProtocols, type RawProtocolRun } from "../adapters/protocol";
import { apiClient } from "../client";
import { queryKeys } from "../query-keys";
import type {
  ActionResponse,
  Clarification,
  CodexRun,
  Feedback,
  FeedbackCreate,
  OpenPRResponse,
  PolicyFinding,
  ProtocolArtifact,
  ProtocolCreate,
  ProtocolFlowInfo,
  ProtocolFromSpecRequest,
  ProtocolFromSpecResponse,
  ProtocolRun,
  ProtocolSpec,
  RunFilters,
  Sprint,
  StepRun,
  SyncResult,
} from "../types";

type RawProtocolFromSpecResponse = Omit<ProtocolFromSpecResponse, "protocol"> & {
  protocol: RawProtocolRun | null;
};
type ProtocolActionResponse = ActionResponse | OpenPRResponse | ProtocolRun;

function adaptOptionalProtocol(protocol: RawProtocolRun | null | undefined): ProtocolRun | null {
  return protocol ? adaptProtocol(protocol) : null;
}

function isProtocolActionStateResponse(data: ProtocolActionResponse): data is ProtocolRun {
  return (
    typeof data === "object" && data !== null && "protocol_name" in data && "project_id" in data
  );
}

const useConditionalRefetchInterval = (baseInterval: number) => {
  if (typeof document === "undefined") return false;
  return document.hidden ? false : baseInterval;
};

// List all Protocols across all projects, optionally filtered by project_id
export function useProtocols(filters?: { project_id?: number }) {
  const refetchInterval = useConditionalRefetchInterval(10000);
  const projectId = filters?.project_id;
  return useQuery({
    queryKey: projectId
      ? [...queryKeys.protocols.all, { project_id: projectId }]
      : queryKeys.protocols.all,
    queryFn: async () => {
      const url = projectId ? `/protocols?project_id=${projectId}` : "/protocols";
      return adaptProtocols(await apiClient.get<RawProtocolRun[]>(url));
    },
    refetchInterval,
  });
}

// List Protocols for Project
export function useProjectProtocols(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.protocols(projectId as number),
    queryFn: async () =>
      adaptProtocols(await apiClient.get<RawProtocolRun[]>(`/projects/${projectId}/protocols`)),
    enabled: !!projectId,
  });
}

// Get Protocol Detail
export function useProtocol(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.detail(id as number),
    queryFn: async () => adaptProtocol(await apiClient.get<RawProtocolRun>(`/protocols/${id}`)),
    enabled: !!id,
  });
}

export const useProtocolDetail = useProtocol;

// Create Protocol
export function useCreateProtocol() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ projectId, data }: { projectId: number; data: ProtocolCreate }) =>
      adaptProtocol(await apiClient.post<RawProtocolRun>(`/projects/${projectId}/protocols`, data)),
    onSuccess: (protocol, { projectId }) => {
      queryClient.setQueryData(queryKeys.protocols.detail(protocol.id), protocol);
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.protocols(projectId),
      });
    },
  });
}

export function useCreateProtocolFromSpec() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: ProtocolFromSpecRequest) => {
      const response = await apiClient.post<RawProtocolFromSpecResponse>(
        "/protocols/from-spec",
        request
      );
      return {
        ...response,
        protocol: adaptOptionalProtocol(response.protocol),
      } satisfies ProtocolFromSpecResponse;
    },
    onSuccess: (response, variables) => {
      if (response.protocol?.project_id) {
        queryClient.setQueryData(
          queryKeys.protocols.detail(response.protocol.id),
          response.protocol
        );
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.protocols(response.protocol.project_id),
        });
      }
      queryClient.invalidateQueries({
        queryKey: queryKeys.specifications.all,
      });
      if (variables.project_id) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.detail(variables.project_id),
        });
      }
    },
  });
}

// Protocol Steps
export function useProtocolSteps(protocolId: number | undefined, enabled = true) {
  const refetchInterval = useConditionalRefetchInterval(5000);
  return useQuery({
    queryKey: queryKeys.protocols.steps(protocolId as number),
    queryFn: () => apiClient.get<StepRun[]>(`/protocols/${protocolId}/steps`),
    enabled: !!protocolId && enabled,
    refetchInterval,
  });
}

// Protocol Runs
export function useProtocolRuns(protocolId: number | undefined, filters?: RunFilters) {
  return useQuery({
    queryKey: queryKeys.protocols.runs(protocolId as number, filters),
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters?.job_type) params.set("job_type", filters.job_type);
      if (filters?.status) params.set("status", filters.status);
      if (filters?.run_kind) params.set("run_kind", filters.run_kind);
      if (filters?.limit) params.set("limit", String(filters.limit));
      const queryString = params.toString();
      return apiClient.get<CodexRun[]>(
        `/protocols/${protocolId}/runs${queryString ? `?${queryString}` : ""}`
      );
    },
    enabled: !!protocolId,
  });
}

// Protocol Spec
export function useProtocolSpec(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.spec(protocolId as number),
    queryFn: () => apiClient.get<ProtocolSpec>(`/protocols/${protocolId}/spec`),
    enabled: !!protocolId,
  });
}

// Protocol Policy
export function useProtocolPolicyFindings(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.policyFindings(protocolId as number),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/protocols/${protocolId}/policy/findings`),
    enabled: !!protocolId,
  });
}

export function useProtocolPolicySnapshot(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.policySnapshot(protocolId as number),
    queryFn: () =>
      apiClient.get<{ hash: string; policy: Record<string, unknown> }>(
        `/protocols/${protocolId}/policy/snapshot`
      ),
    enabled: !!protocolId,
  });
}

// Protocol Clarifications
export function useProtocolClarifications(protocolId: number | undefined, status?: string) {
  const normalizedStatus = status && status !== "all" ? status : undefined;
  return useQuery({
    queryKey: queryKeys.protocols.clarifications(protocolId as number, normalizedStatus),
    queryFn: () =>
      apiClient.get<Clarification[]>(
        `/protocols/${protocolId}/clarifications${normalizedStatus ? `?status=${normalizedStatus}` : ""}`
      ),
    enabled: !!protocolId,
  });
}

// Protocol Actions
export function useProtocolAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      protocolId,
      action,
    }: {
      protocolId: number;
      action:
        | "start"
        | "pause"
        | "resume"
        | "cancel"
        | "run_next_step"
        | "retry_latest"
        | "open_pr";
    }) => {
      const path = `/protocols/${protocolId}/actions/${action}`;
      if (["start", "pause", "resume", "cancel"].includes(action)) {
        return adaptProtocol(await apiClient.post<RawProtocolRun>(path));
      }
      return apiClient.post<ActionResponse | OpenPRResponse>(path);
    },
    onSuccess: (data, { protocolId, action }) => {
      // Show success toast
      const actionMessages: Record<string, string> = {
        start: "Protocol started",
        pause: "Protocol paused",
        resume: "Protocol resumed",
        cancel: "Protocol cancelled",
        run_next_step: "Next step triggered",
        retry_latest: "Step retry initiated",
        open_pr: "Pull request created",
      };
      toast.success(actionMessages[action] || "Action completed");

      if (isProtocolActionStateResponse(data)) {
        queryClient.setQueryData(queryKeys.protocols.detail(protocolId), data);
        queryClient.setQueryData(
          queryKeys.projects.protocols(data.project_id),
          (current: ProtocolRun[] | undefined) => {
            const existing = Array.isArray(current) ? current : [];
            const next = existing.map((protocol) => (protocol.id === data.id ? data : protocol));
            return next.some((protocol) => protocol.id === data.id) ? next : [data, ...existing];
          }
        );
      }

      // Invalidate queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.detail(protocolId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.steps(protocolId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.events(protocolId),
      });
    },
    onError: (error, { action }) => {
      const actionLabels: Record<string, string> = {
        start: "start protocol",
        pause: "pause protocol",
        resume: "resume protocol",
        cancel: "cancel protocol",
        run_next_step: "run next step",
        retry_latest: "retry step",
        open_pr: "create pull request",
      };
      toast.error(`Failed to ${actionLabels[action] || "perform action"}`, {
        description: error instanceof Error ? error.message : undefined,
      });
    },
  });
}

// Protocol Artifacts
export function useProtocolArtifacts(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.artifacts(protocolId as number),
    queryFn: () => apiClient.get<ProtocolArtifact[]>(`/protocols/${protocolId}/artifacts`),
    enabled: !!protocolId,
  });
}

// Protocol Feedback
export function useProtocolFeedback(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.feedback(protocolId as number),
    queryFn: () => apiClient.get<Feedback[]>(`/protocols/${protocolId}/feedback`),
    enabled: !!protocolId,
  });
}

export function useSubmitProtocolFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ protocolId, data }: { protocolId: number; data: FeedbackCreate }) =>
      apiClient.post<Feedback>(`/protocols/${protocolId}/feedback`, data),
    onSuccess: (_, { protocolId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.feedback(protocolId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.detail(protocolId),
      });
    },
  });
}

// Protocol Flow
export function useProtocolFlow(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.flow(protocolId as number),
    queryFn: () => apiClient.get<ProtocolFlowInfo>(`/protocols/${protocolId}/flow`),
    enabled: !!protocolId,
  });
}

export function useCreateProtocolFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (protocolId: number) =>
      apiClient.post<ProtocolFlowInfo>(`/protocols/${protocolId}/flow`),
    onSuccess: (_, protocolId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.flow(protocolId),
      });
    },
  });
}

// Protocol Sprint
export function useProtocolSprint(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.sprint(protocolId as number),
    queryFn: () => apiClient.get<Sprint>(`/protocols/${protocolId}/sprint`),
    enabled: !!protocolId,
  });
}

export function useSyncProtocolToSprint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ protocolId, sprintId }: { protocolId: number; sprintId: number }) =>
      apiClient.post<SyncResult>(`/protocols/${protocolId}/actions/sync-to-sprint`, {
        sprint_id: sprintId,
      }),
    onSuccess: (_, { protocolId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.sprint(protocolId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.detail(protocolId),
      });
    },
  });
}
