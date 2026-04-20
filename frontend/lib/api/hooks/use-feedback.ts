"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";

// =============================================================================
// Types
// =============================================================================

export interface FeedbackEvent {
  id: string;
  protocol_run_id: string;
  step_run_id?: string;
  event_type: string;
  action_taken: string;
  error_type?: string;
  context: Record<string, unknown>;
  created_at: string;
}

export interface FeedbackEventList {
  events: FeedbackEvent[];
  total: number;
}

export interface ClarificationAnswerPayload {
  answer: string | Record<string, unknown>;
}

export interface AnswerClarificationVariables {
  clarificationId: string | number;
  answer: string | Record<string, unknown>;
}

// =============================================================================
// Query Keys
// =============================================================================

export const feedbackKeys = {
  all: ["feedback"] as const,
  byProtocol: (protocolRunId: string | number) =>
    [...feedbackKeys.all, "protocol", String(protocolRunId)] as const,
  byStep: (stepRunId: string | number) => [...feedbackKeys.all, "step", String(stepRunId)] as const,
};

// =============================================================================
// Hooks
// =============================================================================

/**
 * Hook to fetch feedback events for a protocol run
 *
 * @param protocolRunId - The protocol run ID to fetch feedback for
 * @param options - Optional configuration options
 * @returns Query result with feedback events
 */
export function useFeedbackEvents(
  protocolRunId: string | number,
  options?: {
    enabled?: boolean;
  }
) {
  const enabled = options?.enabled ?? true;

  return useQuery({
    queryKey: feedbackKeys.byProtocol(protocolRunId),
    queryFn: () => apiClient.get<FeedbackEventList>(`/protocols/${protocolRunId}/feedback`),
    enabled: enabled && !!protocolRunId,
  });
}

/**
 * Hook to fetch feedback events for a specific step
 *
 * @param stepRunId - The step run ID to fetch feedback for
 * @param options - Optional configuration options
 * @returns Query result with feedback events
 */
export function useStepFeedbackEvents(
  stepRunId: string | number,
  options?: {
    enabled?: boolean;
  }
) {
  const enabled = options?.enabled ?? true;

  return useQuery({
    queryKey: feedbackKeys.byStep(stepRunId),
    queryFn: async () => {
      const result = await apiClient.get<{ events: FeedbackEvent[] }>(`/steps/${stepRunId}/feedback`);
      // API returns {events: [...]} — extract the array
      return Array.isArray(result?.events) ? result.events : Array.isArray(result) ? result : [];
    },
    enabled: enabled && !!stepRunId,
  });
}

/**
 * Hook to answer a clarification question via feedback panel
 *
 * Invalidates relevant queries on success:
 * - Clarifications list
 * - Feedback events
 * - Protocol details
 *
 * @returns Mutation for answering clarifications
 */
export function useFeedbackAnswerClarification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ clarificationId, answer }: AnswerClarificationVariables) =>
      apiClient.post<{ success: boolean; message: string }>(
        `/clarifications/${clarificationId}/answer`,
        { answer }
      ),
    onSuccess: (_, _variables) => {
      // Invalidate clarifications list
      queryClient.invalidateQueries({
        queryKey: queryKeys.clarifications.all,
      });

      // Invalidate feedback events (multiple possible protocols)
      queryClient.invalidateQueries({
        queryKey: feedbackKeys.all,
      });

      // Invalidate protocol clarifications if we have context
      // The answer mutation doesn't return protocol ID, so we invalidate all
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.all,
      });
    },
  });
}

/**
 * Hook to submit feedback on a step
 *
 * @returns Mutation for submitting step feedback
 */
export function useSubmitStepFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      stepRunId,
      action,
      message,
      metadata,
    }: {
      stepRunId: string | number;
      action: "approve" | "reject" | "clarify" | "retry";
      message: string;
      metadata?: Record<string, unknown>;
    }) =>
      apiClient.post<FeedbackEvent>(`/steps/${stepRunId}/feedback`, {
        action,
        message,
        metadata,
      }),
    onSuccess: (_, variables) => {
      // Invalidate step feedback
      queryClient.invalidateQueries({
        queryKey: feedbackKeys.byStep(variables.stepRunId),
      });
      // Also invalidate protocol-level feedback
      queryClient.invalidateQueries({
        queryKey: feedbackKeys.all,
      });
    },
  });
}

/**
 * Hook to trigger a retry for a failed step
 *
 * @returns Mutation for triggering retries
 */
export function useTriggerRetry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ stepRunId, reason }: { stepRunId: string | number; reason?: string }) =>
      apiClient.post<{ success: boolean; job_id?: string }>(`/steps/${stepRunId}/retry`, {
        reason,
      }),
    onSuccess: () => {
      // Invalidate steps and protocols to refresh status
      queryClient.invalidateQueries({
        queryKey: queryKeys.steps.all,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.protocols.all,
      });
      queryClient.invalidateQueries({
        queryKey: feedbackKeys.all,
      });
    },
  });
}

/**
 * Hook to escalate a blocked step
 *
 * @returns Mutation for escalating steps
 */
export function useEscalateStep() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      stepRunId,
      reason,
      assignTo,
    }: {
      stepRunId: string | number;
      reason: string;
      assignTo?: string;
    }) =>
      apiClient.post<{ success: boolean; message: string }>(`/steps/${stepRunId}/escalate`, {
        reason,
        assign_to: assignTo,
      }),
    onSuccess: () => {
      // Invalidate steps and feedback
      queryClient.invalidateQueries({
        queryKey: queryKeys.steps.all,
      });
      queryClient.invalidateQueries({
        queryKey: feedbackKeys.all,
      });
    },
  });
}
