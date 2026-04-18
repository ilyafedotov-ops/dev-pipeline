"use client";

import { useCallback, useContext, useEffect, useRef, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { WebSocketContext, type WebSocketContextValue } from "./context";
import type { StepUpdatePayload, WebSocketServerMessage, WebSocketStatus } from "./types";

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return ctx;
}

export function useWebSocketStatus(): WebSocketStatus {
  return useWebSocket().status;
}

export function useSubscription(
  channel: string | undefined,
  onMessage: (message: WebSocketServerMessage) => void
) {
  const { subscribe } = useWebSocket();
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!channel) return;
    return subscribe(channel, (message) => onMessageRef.current(message));
  }, [channel, subscribe]);
}

export function useProtocolUpdates<TPayload = unknown>(protocolId: number | undefined) {
  const [lastUpdate, setLastUpdate] = useState<WebSocketServerMessage | null>(null);

  useSubscription(protocolId ? `protocol:${protocolId}` : undefined, (message) => {
    setLastUpdate(message);
  });

  return lastUpdate as (WebSocketServerMessage & { payload?: TPayload }) | null;
}

/**
 * Hook to subscribe to step run updates via WebSocket
 * @param stepId - The step ID to subscribe to updates for
 * @returns The latest step update message or null if no updates received
 */
export function useStepUpdates(stepId: number | undefined) {
  const [lastUpdate, setLastUpdate] = useState<WebSocketServerMessage | null>(null);

  useSubscription(stepId ? `step:${stepId}` : undefined, (message) => {
    setLastUpdate(message);
  });

  return lastUpdate as (WebSocketServerMessage & { payload?: StepUpdatePayload }) | null;
}

/**
 * Subscribe to a WebSocket channel and invalidate relevant React Query keys
 * when matching events arrive. Uses the query invalidation pattern for reliable
 * real-time updates with TanStack Query.
 *
 * @param channel - Channel name to subscribe to (e.g. "events", "protocol:1")
 * @param eventTypes - Array of event type strings to react to. If empty, reacts to all events.
 * @param queryKeyOrFn - Either a query key array to invalidate, or a callback
 *   receiving (queryClient, message) for custom invalidation logic.
 */
export function useWebSocketEvent(
  channel: string | undefined,
  eventTypes: string[],
  queryKeyOrFn:
    | readonly unknown[]
    | ((queryClient: ReturnType<typeof useQueryClient>, message: WebSocketServerMessage) => void)
) {
  const queryClient = useQueryClient();
  const queryKeyOrFnRef = useRef(queryKeyOrFn);
  queryKeyOrFnRef.current = queryKeyOrFn;

  const handleMessage = useCallback(
    (message: WebSocketServerMessage) => {
      // Filter by event type if specified
      if (eventTypes.length > 0 && !eventTypes.includes(message.type)) {
        return;
      }
      const target = queryKeyOrFnRef.current;
      if (typeof target === "function") {
        target(queryClient, message);
      } else {
        queryClient.invalidateQueries({ queryKey: [...target] });
      }
    },
    [queryClient, eventTypes]
  );

  // Stabilize eventTypes to avoid resubscribing on every render
  const typesKey = eventTypes.join(",");

  useSubscription(channel, handleMessage);
}

/**
 * Subscribe to multiple WebSocket channels with shared invalidation logic.
 * Useful when a page needs to listen to several channels and invalidate
 * different query keys depending on the channel.
 */
export function useWebSocketEvents(
  subscriptions: Array<{
    channel: string | undefined;
    eventTypes: string[];
    queryKeyOrFn:
      | readonly unknown[]
      | ((queryClient: ReturnType<typeof useQueryClient>, message: WebSocketServerMessage) => void);
  }>
) {
  const queryClient = useQueryClient();
  const subscriptionsRef = useRef(subscriptions);
  subscriptionsRef.current = subscriptions;

  // Collect all unique channels to subscribe to "events" once
  // and dispatch based on the message channel
  const channels = subscriptions
    .map((s) => s.channel)
    .filter((c): c is string => typeof c === "string");

  // Use a single subscription per unique channel
  const uniqueChannels = Array.from(new Set(channels));

  for (const channel of uniqueChannels) {
    const subsForChannel = subscriptions.filter((s) => s.channel === channel);
    const allTypes = subsForChannel.flatMap((s) => s.eventTypes);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useWebSocketEvent(channel, allTypes, (qc, message) => {
      for (const sub of subsForChannel) {
        if (sub.eventTypes.length > 0 && !sub.eventTypes.includes(message.type)) {
          continue;
        }
        const target = sub.queryKeyOrFn;
        if (typeof target === "function") {
          target(qc, message);
        } else {
          qc.invalidateQueries({ queryKey: [...target] });
        }
      }
    });
  }
}
