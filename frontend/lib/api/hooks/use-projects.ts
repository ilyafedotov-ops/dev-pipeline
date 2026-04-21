"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adaptProtocol, type RawProtocolRun } from "../adapters/protocol";
import { apiClient } from "../client";
import { queryKeys } from "../query-keys";
import type {
  ActionResponse,
  ArtifactContent,
  Branch,
  BrownfieldRunRequest,
  BrownfieldRunResponse,
  Clarification,
  Commit,
  DiscoveryRetryResponse,
  EffectivePolicy,
  OnboardingSummary,
  PolicyAuditResult,
  PolicyConfig,
  PolicyFinding,
  Project,
  ProjectCreate,
  ProtocolRun,
  PullRequest,
  WorkItem,
  WorkItemQA,
  WorkItemReview,
  Worktree,
} from "../types";

type RawBrownfieldRunResponse = Omit<BrownfieldRunResponse, "protocol"> & {
  protocol: RawProtocolRun | null;
};

// List Projects
export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => apiClient.get<Project[]>("/projects"),
  });
}

// Get Project Detail
export function useProject(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id as number),
    queryFn: () => apiClient.get<Project>(`/projects/${id}`),
    enabled: !!id,
  });
}

export const useProjectDetail = useProject;

// Create Project
export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => apiClient.post<Project>("/projects", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: number; data: Partial<ProjectCreate> }) =>
      apiClient.put<Project>(`/projects/${projectId}`, data),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    },
  });
}

export function useArchiveProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) => apiClient.post<Project>(`/projects/${projectId}/archive`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    },
  });
}

export function useUnarchiveProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) => apiClient.post<Project>(`/projects/${projectId}/unarchive`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.delete<{ status: string; project_id: number }>(`/projects/${projectId}`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
      queryClient.removeQueries({ queryKey: queryKeys.projects.detail(projectId) });
    },
  });
}

// Onboarding
export function useOnboarding(projectId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.projects.onboarding(projectId as number),
    queryFn: () => apiClient.get<OnboardingSummary>(`/projects/${projectId}/onboarding`),
    enabled: !!projectId && enabled,
    retry: false, // Don't retry - endpoint may not exist
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      if (["completed", "failed"].includes(data.status)) return false;
      return 3000;
    },
  });
}

export function useStartOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.post<ActionResponse>(`/projects/${projectId}/onboarding/actions/start`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.onboarding(projectId),
      });
    },
  });
}

export function useRetryDiscovery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.post<DiscoveryRetryResponse>(`/projects/${projectId}/discovery/actions/retry`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.onboarding(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.discoveryLogs(projectId, 200_000),
      });
    },
  });
}

export function useDiscoveryLogs(
  projectId: number | undefined,
  maxBytes = 200_000,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.projects.discoveryLogs(projectId as number, maxBytes),
    queryFn: () =>
      apiClient.get<ArtifactContent>(`/projects/${projectId}/discovery/logs?max_bytes=${maxBytes}`),
    enabled: !!projectId && enabled,
  });
}

// Policy
export function useProjectPolicy(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policy(projectId as number),
    queryFn: () => apiClient.get<PolicyConfig>(`/projects/${projectId}/policy`),
    enabled: !!projectId,
  });
}

export function useUpdateProjectPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, policy }: { projectId: number; policy: Partial<PolicyConfig> }) =>
      apiClient.put<Project>(`/projects/${projectId}/policy`, policy),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policy(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policyEffective(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policyFindings(projectId),
      });
    },
  });
}

export function useEffectivePolicy(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policyEffective(projectId as number),
    queryFn: () => apiClient.get<EffectivePolicy>(`/projects/${projectId}/policy/effective`),
    enabled: !!projectId,
  });
}

export function usePolicyFindings(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policyFindings(projectId as number),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/projects/${projectId}/policy/findings`),
    enabled: !!projectId,
  });
}

export function useRunPolicyAudit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.post<PolicyAuditResult>(`/projects/${projectId}/policy/audit`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policyFindings(projectId),
      });
    },
  });
}

// Clarifications
export function useProjectClarifications(projectId: number | undefined, status?: string) {
  const normalizedStatus = status && status !== "all" ? status : undefined;
  return useQuery({
    queryKey: queryKeys.projects.clarifications(projectId as number, normalizedStatus),
    queryFn: () =>
      apiClient.get<Clarification[]>(
        `/projects/${projectId}/clarifications${normalizedStatus ? `?status=${normalizedStatus}` : ""}`
      ),
    enabled: !!projectId,
  });
}

export function useAnswerClarification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      scope,
      scopeId,
      key,
      answer,
    }: {
      scope: "project" | "protocol";
      scopeId: number;
      key: string;
      answer: string;
    }) => {
      const path =
        scope === "project"
          ? `/projects/${scopeId}/clarifications/${key}`
          : `/protocols/${scopeId}/clarifications/${key}`;
      return apiClient.post<Clarification>(path, { answer });
    },
    onSuccess: (_, { scope, scopeId }) => {
      if (scope === "project") {
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.clarifications(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.detail(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.onboarding(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.policy(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.policyEffective(scopeId),
        });
      } else {
        queryClient.invalidateQueries({
          queryKey: queryKeys.protocols.clarifications(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.protocols.detail(scopeId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.protocols.policySnapshot(scopeId),
        });
      }
    },
  });
}

// Branches
export function useProjectBranches(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.branches(projectId as number),
    queryFn: () => apiClient.get<Branch[]>(`/projects/${projectId}/branches`),
    enabled: !!projectId,
  });
}

export function useDeleteBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, branch }: { projectId: number; branch: string }) =>
      apiClient.post<ActionResponse>(
        `/projects/${projectId}/branches/${encodeURIComponent(branch)}/delete`
      ),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.branches(projectId),
      });
    },
  });
}

export function useCreateBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      name,
      baseRef,
      checkout,
      push,
    }: {
      projectId: number;
      name: string;
      baseRef?: string;
      checkout?: boolean;
      push?: boolean;
    }) =>
      apiClient.post<ActionResponse>(`/projects/${projectId}/branches`, {
        name,
        base_ref: baseRef,
        checkout: Boolean(checkout),
        push: Boolean(push),
      }),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.branches(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.worktrees(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.pulls(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.commits(projectId) });
    },
  });
}

// Commits
export function useProjectCommits(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.commits(projectId as number),
    queryFn: () => apiClient.get<Commit[]>(`/projects/${projectId}/commits`),
    enabled: !!projectId,
    retry: false, // Don't retry on 5xx — backend may be down, avoid hammering
  });
}

// Pull Requests
export function useProjectPulls(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.pulls(projectId as number),
    queryFn: () => apiClient.get<PullRequest[]>(`/projects/${projectId}/pulls`),
    enabled: !!projectId,
  });
}

// Worktrees (protocol-linked branches)
export function useProjectWorktrees(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.worktrees(projectId as number),
    queryFn: () => apiClient.get<Worktree[]>(`/projects/${projectId}/worktrees`),
    enabled: !!projectId,
  });
}

export function useProjectTaskCycle(projectId: number | undefined, protocolRunId?: number) {
  return useQuery({
    queryKey: queryKeys.projects.taskCycle(projectId as number, protocolRunId),
    queryFn: () => {
      const params = new URLSearchParams();
      if (protocolRunId) params.set("protocol_run_id", String(protocolRunId));
      const query = params.toString();
      return apiClient.get<WorkItem[]>(
        `/projects/${projectId}/task-cycle${query ? `?${query}` : ""}`
      );
    },
    enabled: !!projectId,
  });
}

export function useStartBrownfieldRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      data,
    }: {
      projectId: number;
      data: BrownfieldRunRequest;
    }) => {
      const response = await apiClient.post<RawBrownfieldRunResponse>(
        `/projects/${projectId}/brownfield/run`,
        data,
        {
          projectId,
        }
      );
      return {
        ...response,
        protocol: response.protocol ? adaptProtocol(response.protocol) : null,
      } satisfies BrownfieldRunResponse;
    },
    onSuccess: (response, { projectId }) => {
      if (response.protocol) {
        const protocol = response.protocol;
        queryClient.setQueryData(queryKeys.protocols.detail(protocol.id), protocol);
        queryClient.setQueryData(
          queryKeys.projects.protocols(projectId),
          (current: ProtocolRun[] | undefined) => {
            const existing = Array.isArray(current) ? current : [];
            if (existing.some((existingProtocol) => existingProtocol.id === protocol.id)) {
              return existing;
            }
            return [protocol, ...existing];
          }
        );
        queryClient.setQueryData(
          queryKeys.projects.taskCycle(projectId, protocol.id),
          response.work_items
        );
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.taskCycleRoot(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.protocols(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sprints.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sprints.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    },
  });
}

export function useBuildContextWorkItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      workItemId,
      protocolRunId,
      refresh = false,
    }: {
      projectId: number;
      workItemId: number;
      protocolRunId?: number;
      refresh?: boolean;
    }) =>
      apiClient.post<WorkItem>(`/work-items/${workItemId}/build-context`, { refresh }, { projectId }),
    onSuccess: (workItem, { projectId, protocolRunId, workItemId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycleRoot(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycle(projectId, protocolRunId),
      });
      queryClient.setQueryData(queryKeys.workItems.detail(workItemId), workItem);
    },
  });
}

export function useImplementWorkItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      workItemId,
      protocolRunId,
      data,
    }: {
      projectId: number;
      workItemId: number;
      protocolRunId?: number;
      data?: { owner_agent?: string };
    }) =>
      apiClient.post<WorkItem>(`/work-items/${workItemId}/actions/implement`, data ?? {}, { projectId }),
    onSuccess: (workItem, { projectId, protocolRunId, workItemId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycleRoot(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycle(projectId, protocolRunId),
      });
      queryClient.setQueryData(queryKeys.workItems.detail(workItemId), workItem);
    },
  });
}

export function useReviewWorkItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      workItemId,
      protocolRunId,
    }: {
      projectId: number;
      workItemId: number;
      protocolRunId?: number;
    }) =>
      apiClient.post<WorkItemReview>(`/work-items/${workItemId}/actions/review`, {}, { projectId }),
    onSuccess: (_review, { projectId, protocolRunId, workItemId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycleRoot(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycle(projectId, protocolRunId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.workItems.detail(workItemId) });
    },
  });
}

export function useQaWorkItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      workItemId,
      protocolRunId,
      gates,
    }: {
      projectId: number;
      workItemId: number;
      protocolRunId?: number;
      gates?: string[];
    }) =>
      apiClient.post<WorkItemQA>(`/work-items/${workItemId}/actions/qa`, { gates }, { projectId }),
    onSuccess: (result, { projectId, protocolRunId, workItemId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycleRoot(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycle(projectId, protocolRunId),
      });
      queryClient.setQueryData(queryKeys.workItems.detail(workItemId), result.work_item);
    },
  });
}

export function useMarkPrReady() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      workItemId,
      protocolRunId,
    }: {
      projectId: number;
      workItemId: number;
      protocolRunId?: number;
    }) =>
      apiClient.post<WorkItem>(`/work-items/${workItemId}/actions/mark-pr-ready`, {}, { projectId }),
    onSuccess: (workItem, { projectId, protocolRunId, workItemId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycleRoot(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.taskCycle(projectId, protocolRunId),
      });
      queryClient.setQueryData(queryKeys.workItems.detail(workItemId), workItem);
    },
  });
}

export function useWorkItemArtifactContent(
  workItemId: number | undefined,
  artifactKey: string | null,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.workItems.artifactContent(workItemId as number, artifactKey || "none"),
    queryFn: () =>
      apiClient.get<ArtifactContent>(
        `/work-items/${workItemId}/artifacts/${artifactKey}/content`
      ),
    enabled: !!workItemId && !!artifactKey && enabled,
  });
}
