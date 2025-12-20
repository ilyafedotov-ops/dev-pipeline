"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type {
  Project,
  ProjectCreate,
  OnboardingSummary,
  PolicyConfig,
  PolicyFinding,
  EffectivePolicy,
  Clarification,
  Branch,
  ActionResponse,
} from "../types"

// List Projects
export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => apiClient.get<Project[]>("/projects"),
  })
}

// Get Project Detail
export function useProject(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id!),
    queryFn: () => apiClient.get<Project>(`/projects/${id}`),
    enabled: !!id,
  })
}

export const useProjectDetail = useProject

// Create Project
export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProjectCreate) => apiClient.post<Project>("/projects", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() })
    },
  })
}

export function useArchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => apiClient.post<Project>(`/projects/${projectId}/archive`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() })
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) })
    },
  })
}

export function useUnarchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => apiClient.post<Project>(`/projects/${projectId}/unarchive`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() })
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.delete<{ status: string; project_id: number }>(`/projects/${projectId}`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() })
      queryClient.removeQueries({ queryKey: queryKeys.projects.detail(projectId) })
    },
  })
}

// Onboarding
export function useOnboarding(projectId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.projects.onboarding(projectId!),
    queryFn: () => apiClient.get<OnboardingSummary>(`/projects/${projectId}/onboarding`),
    enabled: !!projectId && enabled,
    retry: false, // Don't retry - endpoint may not exist
    refetchOnWindowFocus: false,
    refetchInterval: false, // Disable polling until data successfully loads
  })
}

export function useStartOnboarding() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) =>
      apiClient.post<ActionResponse>(`/projects/${projectId}/onboarding/actions/start`),
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.onboarding(projectId),
      })
    },
  })
}

// Policy
export function useProjectPolicy(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policy(projectId!),
    queryFn: () => apiClient.get<PolicyConfig>(`/projects/${projectId}/policy`),
    enabled: !!projectId,
  })
}

export function useUpdateProjectPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      policy,
    }: {
      projectId: number
      policy: Partial<PolicyConfig>
    }) => apiClient.put<Project>(`/projects/${projectId}/policy`, policy),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policy(projectId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policyEffective(projectId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.policyFindings(projectId),
      })
    },
  })
}

export function useEffectivePolicy(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policyEffective(projectId!),
    queryFn: () => apiClient.get<EffectivePolicy>(`/projects/${projectId}/policy/effective`),
    enabled: !!projectId,
  })
}

export function usePolicyFindings(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.policyFindings(projectId!),
    queryFn: () => apiClient.get<PolicyFinding[]>(`/projects/${projectId}/policy/findings`),
    enabled: !!projectId,
  })
}

// Clarifications
export function useProjectClarifications(projectId: number | undefined, status?: string) {
  return useQuery({
    queryKey: queryKeys.projects.clarifications(projectId!, status),
    queryFn: () =>
      apiClient.get<Clarification[]>(`/projects/${projectId}/clarifications${status ? `?status=${status}` : ""}`),
    enabled: !!projectId,
  })
}

export function useAnswerClarification() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      scope,
      scopeId,
      key,
      answer,
    }: {
      scope: "project" | "protocol"
      scopeId: number
      key: string
      answer: string
    }) => {
      const path =
        scope === "project"
          ? `/projects/${scopeId}/clarifications/${key}`
          : `/protocols/${scopeId}/clarifications/${key}`
      return apiClient.post<Clarification>(path, { answer })
    },
    onSuccess: (_, { scope, scopeId }) => {
      if (scope === "project") {
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.clarifications(scopeId),
        })
        queryClient.invalidateQueries({
          queryKey: queryKeys.projects.onboarding(scopeId),
        })
      } else {
        queryClient.invalidateQueries({
          queryKey: queryKeys.protocols.clarifications(scopeId),
        })
      }
    },
  })
}

// Branches
export function useProjectBranches(projectId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.branches(projectId!),
    queryFn: () => apiClient.get<Branch[]>(`/projects/${projectId}/branches`),
    enabled: !!projectId,
  })
}

export function useDeleteBranch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      branch,
    }: {
      projectId: number
      branch: string
    }) => apiClient.post<ActionResponse>(`/projects/${projectId}/branches/${encodeURIComponent(branch)}/delete`),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects.branches(projectId),
      })
    },
  })
}
