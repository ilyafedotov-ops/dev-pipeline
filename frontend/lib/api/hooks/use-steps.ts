"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { CodexRun, PolicyFinding, ActionResponse } from "../types"

// Step Runs
export function useStepRuns(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.runs(stepId!),
    queryFn: () => apiClient.get<CodexRun[]>(`/steps/${stepId}/runs`),
    enabled: !!stepId,
  })
}

// Step Policy Findings
export function useStepPolicyFindings(stepId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.steps.policyFindings(stepId!),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/steps/${stepId}/policy/findings`),
    enabled: !!stepId,
  })
}

// Step Actions
export function useStepAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      stepId,
      action,
    }: {
      stepId: number
      protocolId: number
      action: "run" | "run_qa" | "approve"
    }) => apiClient.post<ActionResponse>(`/steps/${stepId}/actions/${action}`),
    onSuccess: (_, { stepId, protocolId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.steps.runs(stepId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.steps(protocolId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.events(protocolId),
      })
    },
  })
}
