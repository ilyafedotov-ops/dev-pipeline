import useSWR, { mutate } from "swr"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { Sprint, SprintCreate, AgileTask, AgileTaskCreate, AgileTaskUpdate, SprintMetrics } from "../types"
export function useSprints(projectId: number) {
  return useSWR<Sprint[]>(queryKeys.sprints.byProject(projectId), async () => {
    return apiClient.get<Sprint[]>(`/projects/${projectId}/sprints`)
  })
}

export function useAllSprints() {
  return useSWR<Sprint[]>(queryKeys.sprints.all, async () => {
    return apiClient.get<Sprint[]>("/sprints")
  })
}

export function useSprint(sprintId: number) {
  return useSWR<Sprint>(queryKeys.sprints.detail(sprintId), async () => {
    return apiClient.get<Sprint>(`/sprints/${sprintId}`)
  })
}

export function useSprintMetrics(sprintId: number) {
  return useSWR<SprintMetrics>(queryKeys.sprints.metrics(sprintId), async () => {
    return apiClient.get<SprintMetrics>(`/sprints/${sprintId}/metrics`)
  })
}

export function useTasks(projectId: number, sprintId?: number | null) {
  return useSWR<AgileTask[]>(queryKeys.tasks.byProject(projectId, sprintId), async () => {
    const params = sprintId ? `?sprint_id=${sprintId}` : ""
    return apiClient.get<AgileTask[]>(`/projects/${projectId}/tasks${params}`)
  })
}

export function useAllTasks() {
  return useSWR<AgileTask[]>(queryKeys.tasks.all, async () => {
    return apiClient.get<AgileTask[]>("/tasks")
  })
}

export function useTask(taskId: number) {
  return useSWR<AgileTask>(queryKeys.tasks.detail(taskId), async () => {
    return apiClient.get<AgileTask>(`/tasks/${taskId}`)
  })
}

export function useCreateTask() {
  return {
    mutateAsync: async (projectId: number, data: AgileTaskCreate) => {
      const result = await apiClient.post<AgileTask>(`/projects/${projectId}/tasks`, data)
      mutate(queryKeys.tasks.byProject(projectId, data.sprint_id))
      return result
    },
    isPending: false,
  }
}

export function useUpdateTask() {
  return {
    mutateAsync: async (taskId: number, data: AgileTaskUpdate) => {
      const result = await apiClient.patch<AgileTask>(`/tasks/${taskId}`, data)
      mutate(queryKeys.tasks.detail(taskId))
      return result
    },
    isPending: false,
  }
}

export function useCreateSprint() {
  return {
    mutateAsync: async (projectId: number, data: SprintCreate) => {
      const result = await apiClient.post<Sprint>(`/sprints`, { ...data, project_id: projectId })
      mutate(queryKeys.sprints.byProject(projectId))
      return result
    },
    isPending: false,
  }
}
