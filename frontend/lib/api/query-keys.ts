// Query key factory for TanStack Query
import type { RunFilters, EventFilters } from "./types"

export const queryKeys = {
  // Health
  health: ["health"] as const,

  // Projects
  projects: {
    all: ["projects"] as const,
    list: () => [...queryKeys.projects.all, "list"] as const,
    detail: (id: number) => [...queryKeys.projects.all, "detail", id] as const,
    onboarding: (id: number) => [...queryKeys.projects.all, "onboarding", id] as const,
    protocols: (id: number) => [...queryKeys.projects.all, "protocols", id] as const,
    policy: (id: number) => [...queryKeys.projects.all, "policy", id] as const,
    policyEffective: (id: number) => [...queryKeys.projects.all, "policyEffective", id] as const,
    policyFindings: (id: number) => [...queryKeys.projects.all, "policyFindings", id] as const,
    clarifications: (id: number, status?: string) =>
      [...queryKeys.projects.all, "clarifications", id, { status }] as const,
    branches: (id: number) => [...queryKeys.projects.all, "branches", id] as const,
  },

  // Protocols
  protocols: {
    all: ["protocols"] as const,
    detail: (id: number) => [...queryKeys.protocols.all, "detail", id] as const,
    steps: (id: number) => [...queryKeys.protocols.all, "steps", id] as const,
    events: (id: number) => [...queryKeys.protocols.all, "events", id] as const,
    runs: (id: number, filters?: RunFilters) => [...queryKeys.protocols.all, "runs", id, filters] as const,
    spec: (id: number) => [...queryKeys.protocols.all, "spec", id] as const,
    policyFindings: (id: number) => [...queryKeys.protocols.all, "policyFindings", id] as const,
    policySnapshot: (id: number) => [...queryKeys.protocols.all, "policySnapshot", id] as const,
    clarifications: (id: number, status?: string) =>
      [...queryKeys.protocols.all, "clarifications", id, { status }] as const,
  },

  // Steps
  steps: {
    all: ["steps"] as const,
    detail: (id: number) => [...queryKeys.steps.all, "detail", id] as const,
    runs: (id: number) => [...queryKeys.steps.all, "runs", id] as const,
    policyFindings: (id: number) => [...queryKeys.steps.all, "policyFindings", id] as const,
  },

  // Runs
  runs: {
    all: ["runs"] as const,
    list: (filters: RunFilters) => [...queryKeys.runs.all, "list", filters] as const,
    detail: (runId: string) => [...queryKeys.runs.all, "detail", runId] as const,
    logs: (runId: string) => [...queryKeys.runs.all, "logs", runId] as const,
    artifacts: (runId: string) => [...queryKeys.runs.all, "artifacts", runId] as const,
  },

  // Policy Packs
  policyPacks: {
    all: ["policyPacks"] as const,
    list: () => [...queryKeys.policyPacks.all, "list"] as const,
    detail: (key: string) => [...queryKeys.policyPacks.all, "detail", key] as const,
  },

  // Operations
  ops: {
    queueStats: ["ops", "queueStats"] as const,
    queueJobs: (status?: string) => ["ops", "queueJobs", { status }] as const,
    recentEvents: (filters: EventFilters) => ["ops", "recentEvents", filters] as const,
    metricsSummary: (hours?: number) => ["ops", "metricsSummary", { hours }] as const,
  },

  // Sprints and Tasks for Agile system
  sprints: {
    all: ["sprints"] as const,
    byProject: (projectId: number) => ["sprints", "project", projectId] as const,
    detail: (id: number) => ["sprints", "detail", id] as const,
    metrics: (id: number) => ["sprints", "metrics", id] as const,
  },

  tasks: {
    all: ["tasks"] as const,
    byProject: (projectId: number, sprintId?: number | null) => ["tasks", "project", projectId, { sprintId }] as const,
    detail: (id: number) => ["tasks", "detail", id] as const,
  },

  // Agents
  agents: {
    all: ["agents"] as const,
    list: (projectId?: number) => [...queryKeys.agents.all, "list", projectId ?? "global"] as const,
    detail: (id: string) => [...queryKeys.agents.all, "detail", id] as const,
    defaults: (projectId?: number) => [...queryKeys.agents.all, "defaults", projectId ?? "global"] as const,
    prompts: (projectId?: number) => [...queryKeys.agents.all, "prompts", projectId ?? "global"] as const,
    health: (projectId?: number) => [...queryKeys.agents.all, "health", projectId ?? "global"] as const,
    metrics: (projectId?: number) => [...queryKeys.agents.all, "metrics", projectId ?? "global"] as const,
    project: (projectId: number) => [...queryKeys.agents.all, "project", projectId] as const,
  },

  // Clarifications
  clarifications: {
    all: ["clarifications"] as const,
    list: (status?: string) => [...queryKeys.clarifications.all, "list", status ?? "all"] as const,
  },

  // Specifications
  specifications: {
    all: ["specifications"] as const,
    list: (projectId?: number, filters?: Record<string, unknown>) => [...queryKeys.specifications.all, "list", { projectId, ...filters }] as const,
    detail: (id: number) => [...queryKeys.specifications.all, "detail", id] as const,
    content: (id: number) => [...queryKeys.specifications.all, "content", id] as const,
  },

  // SpecKit
  speckit: {
    status: (projectId: number) => ["speckit", "status", projectId] as const,
    constitution: (projectId: number) => ["speckit", "constitution", projectId] as const,
    specs: (projectId: number) => ["speckit", "specs", projectId] as const,
    checklist: (projectId: number, specPath?: string) => ["speckit", "checklist", projectId, specPath] as const,
    analysis: (projectId: number, specPath?: string) => ["speckit", "analysis", projectId, specPath] as const,
    implement: (projectId: number, specPath?: string) => ["speckit", "implement", projectId, specPath] as const,
  },

  // Quality
  quality: {
    all: ["quality"] as const,
    dashboard: () => [...queryKeys.quality.all, "dashboard"] as const,
  },

  // Profile
  profile: {
    all: ["profile"] as const,
    me: () => [...queryKeys.profile.all, "me"] as const,
  },
}
