"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { Clarification } from "../types"

export function useClarifications(status?: string) {
  return useQuery({
    queryKey: queryKeys.clarifications.list(status),
    queryFn: () => apiClient.get<Clarification[]>(`/clarifications${status ? `?status=${status}` : ""}`),
  })
}

export function useAnswerClarificationById() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, answer }: { id: number; answer: string }) =>
      apiClient.post<Clarification>(`/clarifications/${id}/answer`, { answer }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clarifications.all })
    },
  })
}
