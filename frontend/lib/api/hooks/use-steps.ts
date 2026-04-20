"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";
import type {
  ActionResponse,
  ArtifactContent,
  CodexRun,
  PolicyFinding,
  StepArtifact,
  StepQuality,
  StepRun,
} from "../types";

// Step Runs

/**
 * Fetch a single step by ID directly from the API.
 * This is the primary data source for the step detail page.
 */
export function useStepRun(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.detail(stepId as number),
    queryFn: () => apiClient.get<StepRun>(`/steps/${stepId}`),
    enabled: !!stepId,
  });
}

export function useStepRuns(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.runs(stepId as number),
    queryFn: () => apiClient.get<CodexRun[]>(`/steps/${stepId}/runs`),
    enabled: !!stepId,
  });
}

// Step Policy Findings
export function useStepPolicyFindings(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.policyFindings(stepId as number),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/steps/${stepId}/policy/findings`),
    enabled: !!stepId,
  });
}

// Step Actions
export function useStepAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      stepId,
      action,
    }: {
      stepId: number;
      protocolId: number;
      action: "execute" | "qa";
    }) => apiClient.post<ActionResponse>(`/steps/${stepId}/actions/${action}`),
    onSuccess: (_, { stepId, protocolId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.steps.runs(stepId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.steps(protocolId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.events(protocolId),
      });
    },
  });
}

// Step Artifacts
export function useStepArtifacts(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.artifacts(stepId as number),
    queryFn: () => apiClient.get<StepArtifact[]>(`/steps/${stepId}/artifacts`),
    enabled: !!stepId,
  });
}

export function useStepArtifactContent(stepId: number | undefined, artifactId: number | undefined) {
  return useQuery({
    queryKey: [...queryKeys.steps.artifacts(stepId as number), "content", artifactId],
    queryFn: () =>
      apiClient.get<ArtifactContent>(`/steps/${stepId}/artifacts/${artifactId}/content`),
    enabled: !!stepId && !!artifactId,
  });
}

export function useStepArtifactDownloadUrl(stepId: number, artifactId: number) {
  const config = apiClient.getConfig();
  return `${config.baseUrl}/steps/${stepId}/artifacts/${artifactId}/download`;
}

// Step Quality
export function useStepQuality(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.quality(stepId as number),
    queryFn: () => apiClient.get<StepQuality>(`/steps/${stepId}/quality`),
    enabled: !!stepId,
  });
}

export function useAssignStepAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ stepId, agentId }: { stepId: number; protocolId: number; agentId: string }) =>
      apiClient.post<ActionResponse>(`/steps/${stepId}/actions/assign_agent`, {
        agent_id: agentId,
      }),
    onSuccess: (_, { stepId, protocolId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.protocols.steps(protocolId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.steps.runs(stepId) });
    },
  });
}
