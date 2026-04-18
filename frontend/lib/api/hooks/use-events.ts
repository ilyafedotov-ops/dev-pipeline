"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import { useVisibility } from "@/lib/hooks/use-visibility";
import { useSubscription } from "@/lib/websocket/hooks";
import type { WebSocketServerMessage } from "@/lib/websocket/types";

import { apiClient, ApiError } from "../client";
import { queryKeys } from "../query-keys";
import type { Event as DevGodzillaEvent } from "../types";

// =============================================================================
// Types
// =============================================================================

export interface EventListResponse {
  events: DevGodzillaEvent[];
  total: number;
}

export interface EventStreamFilters {
  protocol_id?: number;
  project_id?: number;
  event_type?: string;
  categories?: string[];
  since_id?: number;
}

export interface EventStreamState {
  status: "idle" | "connecting" | "open" | "error";
  lastEventId: number;
}

/**
 * WebSocket-based event stream state
 */
export interface WebSocketEventStreamState {
  events: DevGodzillaEvent[];
  lastEventId: number;
  isConnected: boolean;
}

/**
 * Hook to subscribe to real-time events via WebSocket
 * Implements Requirement 10.1: Real-time events using WebSocket
 *
 * @param filters - Optional filters for events (event_type filtering is done client-side)
 * @param options - Configuration options
 * @returns WebSocket event stream state with events array
 */
export function useWebSocketEventStream(
  filters?: EventStreamFilters | null,
  options?: {
    enabled?: boolean;
    maxEvents?: number;
    onEvent?: (event: DevGodzillaEvent) => void;
  }
): WebSocketEventStreamState {
  const [events, setEvents] = useState<DevGodzillaEvent[]>([]);
  const [lastEventId, setLastEventId] = useState(0);
  const [isConnected, setIsConnected] = useState(false);

  const enabled = options?.enabled ?? true;
  const maxEvents = options?.maxEvents ?? 200;
  const onEventRef = useRef(options?.onEvent);
  onEventRef.current = options?.onEvent;

  const handleMessage = useCallback(
    (message: WebSocketServerMessage) => {
      if (message.type !== "event" || !message.payload) return;

      const event = message.payload as DevGodzillaEvent;
      if (typeof event?.id !== "number") return;

      // Apply client-side filters
      if (filters) {
        // Filter by protocol_id if specified
        if (
          typeof filters.protocol_id === "number" &&
          event.protocol_run_id !== filters.protocol_id
        ) {
          return;
        }
        // Filter by project_id if specified
        if (typeof filters.project_id === "number" && event.project_id !== filters.project_id) {
          return;
        }
        // Filter by event_type if specified
        if (filters.event_type && event.event_type !== filters.event_type) {
          return;
        }
        // Filter by categories if specified
        if (filters.categories && filters.categories.length > 0) {
          if (!event.event_category || !filters.categories.includes(event.event_category)) {
            return;
          }
        }
      }

      setLastEventId((prev) => Math.max(prev, event.id));
      setEvents((prev) => {
        const next = [event, ...prev];
        // Deduplicate by id
        const unique = new Map<number, DevGodzillaEvent>();
        for (const e of next) unique.set(e.id, e);
        return Array.from(unique.values()).slice(0, maxEvents);
      });

      onEventRef.current?.(event);
    },
    [filters, maxEvents]
  );

  // Subscribe to the events channel via WebSocket
  useSubscription(enabled ? "events" : undefined, handleMessage);

  // Track connection state
  useEffect(() => {
    if (enabled) {
      setIsConnected(true);
    } else {
      setIsConnected(false);
    }
  }, [enabled]);

  // Reset events when filters change
  useEffect(() => {
    setEvents([]);
    setLastEventId(0);
  }, [filters?.protocol_id, filters?.project_id]);

  return { events, lastEventId, isConnected };
}

// =============================================================================
// Data-fetching hooks
// =============================================================================

/**
 * Fetch recent events with optional limit.
 * GET /api/v1/events?limit=N
 */
export function useEvents(limit?: number) {
  const refetchInterval = useConditionalRefetchInterval(10_000);
  return useQuery({
    queryKey: queryKeys.events.list(limit),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (limit) params.set("limit", String(limit));
      const qs = params.toString();
      return apiClient.get<DevGodzillaEvent[]>(`/events${qs ? `?${qs}` : ""}`);
    },
    refetchInterval,
  });
}

/**
 * Utility function to filter events by type
 * Implements Property 13: Event feed filtering consistency
 *
 * @param events - Array of events to filter
 * @param eventType - Event type to filter by (or "all" for no filtering)
 * @returns Filtered events array
 */
export function filterEventsByType(
  events: DevGodzillaEvent[],
  eventType: string
): DevGodzillaEvent[] {
  if (!eventType || eventType === "all") {
    return events;
  }
  return events.filter((e) => e.event_type === eventType);
}

/**
 * Utility function to check if an event has a protocol link
 * Implements Property 14: Event feed protocol links
 *
 * @param event - Event to check
 * @returns True if the event has a protocol_run_id
 */
export function eventHasProtocolLink(event: DevGodzillaEvent): boolean {
  return typeof event.protocol_run_id === "number" && event.protocol_run_id !== null;
}

/**
 * Get unique event types from an array of events
 *
 * @param events - Array of events
 * @returns Sorted array of unique event types
 */
export function getUniqueEventTypes(events: DevGodzillaEvent[]): string[] {
  const set = new Set(events.map((e) => e.event_type).filter(Boolean));
  return Array.from(set).sort();
}

export function useEventStream(
  filters: EventStreamFilters | null,
  options?: {
    enabled?: boolean;
    onEvent?: (event: DevGodzillaEvent) => void;
  }
): EventStreamState {
  const [state, setState] = useState<EventStreamState>({ status: "idle", lastEventId: 0 });
  const onEventRef = useRef(options?.onEvent);
  onEventRef.current = options?.onEvent;

  const enabled = options?.enabled ?? true;

  const streamUrl = useMemo(() => {
    if (!enabled || !filters) return null;

    const params = new URLSearchParams();
    if (typeof filters.protocol_id === "number")
      {params.set("protocol_id", String(filters.protocol_id));}
    if (typeof filters.project_id === "number")
      {params.set("project_id", String(filters.project_id));}
    if (filters.event_type) params.set("event_type", filters.event_type);
    for (const category of filters.categories ?? []) {
      if (category) params.append("category", category);
    }
    if (typeof filters.since_id === "number" && filters.since_id > 0)
      {params.set("since_id", String(filters.since_id));}

    const { baseUrl, token } = apiClient.getConfig();
    if (token) params.set("token", token);

    const normalizedBase = (baseUrl || "").replace(/\/$/, "");
    const path = `/events/stream?${params.toString()}`;
    return normalizedBase ? `${normalizedBase}${path}` : path;
  }, [enabled, filters]);

  useEffect(() => {
    if (!streamUrl) {
      setState({ status: "idle", lastEventId: 0 });
      return;
    }

    let cancelled = false;
    setState((prev) => ({ ...prev, status: "connecting" }));

    const source = new EventSource(streamUrl);

    source.onopen = () => {
      if (cancelled) return;
      setState((prev) => ({ ...prev, status: "open" }));
    };

    source.onmessage = (message) => {
      if (cancelled) return;
      try {
        const payload = JSON.parse(message.data) as DevGodzillaEvent;
        if (typeof payload?.id === "number") {
          setState((prev) => ({ ...prev, lastEventId: Math.max(prev.lastEventId, payload.id) }));
        }
        onEventRef.current?.(payload);
      } catch {
        // Ignore malformed frames
      }
    };

    source.onerror = () => {
      if (cancelled) return;
      setState((prev) => ({ ...prev, status: "error" }));
    };

    return () => {
      cancelled = true;
      source.close();
    };
  }, [streamUrl]);

  return state;
}

function useConditionalRefetchInterval(baseInterval: number) {
  const isVisible = useVisibility();
  return isVisible ? baseInterval : false;
}

export function useProtocolEvents(protocolId: number | undefined, enabled = true) {
  const refetchInterval = useConditionalRefetchInterval(5000);
  return useQuery({
    queryKey: queryKeys.protocols.events(protocolId as number),
    queryFn: () => apiClient.get<DevGodzillaEvent[]>(`/protocols/${protocolId}/events`),
    enabled: !!protocolId && enabled,
    refetchInterval,
  });
}

export function useEventsStreamFallbackError(filters: EventStreamFilters | null) {
  const streamState = useEventStream(filters, { enabled: Boolean(filters) });
  if (streamState.status !== "error") return null;
  // Best-effort hint: if API requires token and none was provided, SSE can fail.
  const token = apiClient.getConfig().token;
  if (!token)
    {return new ApiError("SSE stream failed; API token may be required (configure in UI).", 401);}
  return new ApiError("SSE stream failed; check backend connectivity.", 0);
}
