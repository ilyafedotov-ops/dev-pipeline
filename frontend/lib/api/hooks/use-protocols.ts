"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type {
  ProtocolRun,
  ProtocolCreate,
  ProtocolSpec,
  ProtocolFromSpecRequest,
  ProtocolFromSpecResponse,
  StepRun,
  Event,
  CodexRun,
  PolicyFinding,
  Clarification,
  ActionResponse,
  RunFilters,
} from "../types"

const useConditionalRefetchInterval = (baseInterval: number) => {
  if (typeof document === "undefined") return false
  return document.hidden ? false : baseInterval
}

// List all Protocols across all projects
export function useProtocols() {
  const refetchInterval = useConditionalRefetchInterval(10000)
  return useQuery({
    queryKey: queryKeys.protocols.all,
    queryFn: () => apiClient.get<ProtocolRun[]>("/protocols"),
    refetchInterval,
  })
}

// List Protocols for Project
export function useProjectProtocols(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.protocols(projectId!),
    queryFn: () => apiClient.get<ProtocolRun[]>(`/projects/${projectId}/protocols`),
    enabled: !!projectId,
  })
}

// Get Protocol Detail
export function useProtocol(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.detail(id!),
    queryFn: () => apiClient.get<ProtocolRun>(`/protocols/${id}`),
    enabled: !!id,
  })
}

export const useProtocolDetail = useProtocol

// Create Protocol
export function useCreateProtocol() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: number
      data: ProtocolCreate
    }) => apiClient.post<ProtocolRun>(`/projects/${projectId}/protocols`, data),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.protocols(projectId),
      })
    },
  })
}

export function useCreateProtocolFromSpec() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: ProtocolFromSpecRequest) =>
      apiClient.post<ProtocolFromSpecResponse>("/protocols/from-spec", request),
    onSuccess: (response, variables) => {
      if (response.protocol?.project_id) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.protocols(response.protocol.project_id),
        })
      }
      queryClient.invalidateQueries({
        queryKey: queryKeys.specifications.all,
      })
      if (variables.project_id) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.detail(variables.project_id),
        })
      }
    },
  })
}

// Protocol Steps
export function useProtocolSteps(protocolId: number | undefined, enabled = true) {
  const refetchInterval = useConditionalRefetchInterval(5000)
  return useQuery({
    queryKey: queryKeys.protocols.steps(protocolId!),
    queryFn: () => apiClient.get<StepRun[]>(`/protocols/${protocolId}/steps`),
    enabled: !!protocolId && enabled,
    refetchInterval,
  })
}

// Protocol Events
export function useProtocolEvents(protocolId: number | undefined, enabled = true) {
  const refetchInterval = useConditionalRefetchInterval(5000)
  return useQuery({
    queryKey: queryKeys.protocols.events(protocolId!),
    queryFn: () => apiClient.get<Event[]>(`/protocols/${protocolId}/events`),
    enabled: !!protocolId && enabled,
    refetchInterval,
  })
}

// Protocol Runs
export function useProtocolRuns(protocolId: number | undefined, filters?: RunFilters) {
  return useQuery({
    queryKey: queryKeys.protocols.runs(protocolId!, filters),
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters?.job_type) params.set("job_type", filters.job_type)
      if (filters?.status) params.set("status", filters.status)
      if (filters?.run_kind) params.set("run_kind", filters.run_kind)
      if (filters?.limit) params.set("limit", String(filters.limit))
      const queryString = params.toString()
      return apiClient.get<CodexRun[]>(`/protocols/${protocolId}/runs${queryString ? `?${queryString}` : ""}`)
    },
    enabled: !!protocolId,
  })
}

// Protocol Spec
export function useProtocolSpec(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.spec(protocolId!),
    queryFn: () => apiClient.get<ProtocolSpec>(`/protocols/${protocolId}/spec`),
    enabled: !!protocolId,
  })
}

// Protocol Policy
export function useProtocolPolicyFindings(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.policyFindings(protocolId!),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/protocols/${protocolId}/policy/findings`),
    enabled: !!protocolId,
  })
}

export function useProtocolPolicySnapshot(protocolId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.protocols.policySnapshot(protocolId!),
    queryFn: () =>
      apiClient.get<{ hash: string; policy: Record<string, unknown> }>(`/protocols/${protocolId}/policy/snapshot`),
    enabled: !!protocolId,
  })
}

// Protocol Clarifications
export function useProtocolClarifications(protocolId: number | undefined, status?: string) {
  return useQuery({
    queryKey: queryKeys.protocols.clarifications(protocolId!, status),
    queryFn: () =>
      apiClient.get<Clarification[]>(`/protocols/${protocolId}/clarifications${status ? `?status=${status}` : ""}`),
    enabled: !!protocolId,
  })
}

// Protocol Actions
export function useProtocolAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      protocolId,
      action,
    }: {
      protocolId: number
      action: "start" | "pause" | "resume" | "cancel" | "run_next_step" | "retry_latest" | "open_pr"
    }) => apiClient.post<ActionResponse>(`/protocols/${protocolId}/actions/${action}`),
    onSuccess: (_, { protocolId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.detail(protocolId),
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
