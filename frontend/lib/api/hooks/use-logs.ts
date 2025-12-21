"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useCallback, useState } from "react"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"
import type { AppLogEntry, AppLogFilters } from "../types"

export function useRecentLogs(filters: AppLogFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.ops.recentLogs(filters),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.level) params.set("level", filters.level)
      if (filters.source) params.set("source", filters.source)
      if (filters.limit) params.set("limit", String(filters.limit))
      const queryString = params.toString()
      const response = await apiClient.get<{ logs: AppLogEntry[] }>(
        `/logs/recent${queryString ? `?${queryString}` : ""}`
      )
      return response.logs
    },
    enabled: options?.enabled ?? true,
    refetchInterval: 5000,
  })
}

export interface UseLogStreamOptions {
  level?: string
  source?: string
  onLog: (log: AppLogEntry) => void
  onError?: (error: Event) => void
  onConnected?: () => void
  enabled?: boolean
}

export function useLogStream({
  level,
  source,
  onLog,
  onError,
  onConnected,
  enabled = true,
}: UseLogStreamOptions) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const lastIdRef = useRef<number>(0)
  const [isConnected, setIsConnected] = useState(false)

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    if (!enabled || typeof window === "undefined" || typeof EventSource === "undefined") {
      return cleanup
    }

    const params = new URLSearchParams()
    params.set("since_id", String(lastIdRef.current))
    if (level) params.set("level", level)
    if (source) params.set("source", source)

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || ""
    const streamUrl = `${baseUrl}/logs/stream?${params.toString()}`

    const source$ = new EventSource(streamUrl)
    eventSourceRef.current = source$

    const handleLogEvent = (event: MessageEvent) => {
      try {
        const log = JSON.parse(event.data) as AppLogEntry
        if (log.id) {
          lastIdRef.current = Math.max(lastIdRef.current, log.id)
        }
        onLog(log)
      } catch {
        // Ignore malformed events
      }
    }

    const handleConnected = () => {
      setIsConnected(true)
      onConnected?.()
    }

    const handleError = (event: Event) => {
      setIsConnected(false)
      onError?.(event)
      source$.close()
      eventSourceRef.current = null
    }

    source$.addEventListener("log", handleLogEvent)
    source$.addEventListener("connected", handleConnected)
    source$.addEventListener("error", handleError)

    return () => {
      source$.removeEventListener("log", handleLogEvent)
      source$.removeEventListener("connected", handleConnected)
      source$.removeEventListener("error", handleError)
      cleanup()
    }
  }, [enabled, level, source, onLog, onError, onConnected, cleanup])

  return {
    close: cleanup,
    isConnected,
  }
}
