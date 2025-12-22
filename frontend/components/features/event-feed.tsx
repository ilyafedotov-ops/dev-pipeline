"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Activity,
  ChevronDown,
  GitBranch,
  GitCommit,
  GitPullRequest,
  Play as PlayIcon,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Pause,
  Play,
  RefreshCw,
  Wifi,
  WifiOff,
  Cog,
  FileText,
  Zap,
  Shield,
  Search,
  Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelativeTime } from "@/lib/format"
import type { Event } from "@/lib/api/types"
import {
  useWebSocketEventStream,
  filterEventsByType,
  eventHasProtocolLink,
  getUniqueEventTypes
} from "@/lib/api/hooks/use-events"

const MAX_EVENTS = 200

export interface EventFeedProps {
  protocolId?: number
  projectId?: number
}

/**
 * EventFeed component displays real-time events via WebSocket
 * 
 * Implements:
 * - Requirement 10.1: Real-time events using WebSocket
 * - Requirement 10.2: Filter by event type
 * - Requirement 10.3: Links to related protocols
 */
export function EventFeed({
  protocolId,
  projectId,
}: EventFeedProps) {
  const [paused, setPaused] = useState(false)
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all")
  const [search, setSearch] = useState("")

  // Use WebSocket-based event stream
  const { events, lastEventId, isConnected } = useWebSocketEventStream(
    {
      protocol_id: protocolId,
      project_id: projectId,
    },
    {
      enabled: !paused,
      maxEvents: MAX_EVENTS,
    }
  )

  // Filter events by type (Property 13: Event feed filtering consistency)
  const filteredByType = useMemo(() => {
    return filterEventsByType(events, eventTypeFilter)
  }, [events, eventTypeFilter])

  // Apply search filter
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return filteredByType
    
    return filteredByType.filter((e) => {
      const blob = `${e.event_type} ${e.message} ${e.project_name ?? ""} ${e.protocol_name ?? ""}`.toLowerCase()
      return blob.includes(q)
    })
  }, [filteredByType, search])

  // Get available event types for filter dropdown
  const availableEventTypes = useMemo(() => {
    return getUniqueEventTypes(events)
  }, [events])

  const handleClear = () => {
    // Note: Since we're using WebSocket, we can't clear the server-side events
    // This would require a state reset mechanism
    window.location.reload()
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Event Feed
            </CardTitle>
            <CardDescription className="flex items-center gap-2">
              Real-time updates via WebSocket
              <span className="flex items-center gap-1">
                {isConnected && !paused ? (
                  <Wifi className="h-3 w-3 text-green-500" />
                ) : (
                  <WifiOff className="h-3 w-3 text-muted-foreground" />
                )}
                {paused ? "paused" : isConnected ? "connected" : "disconnected"}
              </span>
              • last id: {lastEventId}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleClear}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Clear
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPaused((p) => !p)}>
              {paused ? <Play className="h-4 w-4 mr-2" /> : <Pause className="h-4 w-4 mr-2" />}
              {paused ? "Resume" : "Pause"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input 
            value={search} 
            onChange={(e) => setSearch(e.target.value)} 
            placeholder="Search…" 
            className="w-64" 
          />
          <Select value={eventTypeFilter} onValueChange={setEventTypeFilter}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Event type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All event types</SelectItem>
              {availableEventTypes.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="text-xs text-muted-foreground">{filtered.length} shown</div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6">No events yet.</div>
        ) : (
          <div className="space-y-2">
            {filtered.map((e) => (
              <EventItem key={e.id} event={e} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function getEventIcon(eventType: string, category?: string | null) {
  const type = eventType.toLowerCase()
  if (type.includes("git_branch") || type.includes("branch")) return GitBranch
  if (type.includes("git_commit") || type.includes("commit")) return GitCommit
  if (type.includes("git_pull") || type.includes("pr_") || type.includes("pull_request")) return GitPullRequest
  if (type.includes("started") || type.includes("running")) return PlayIcon
  if (type.includes("completed") || type.includes("success")) return CheckCircle2
  if (type.includes("failed") || type.includes("error")) return XCircle
  if (type.includes("warning") || type.includes("paused")) return AlertCircle
  if (type.includes("discovery") || type.includes("search")) return Search
  if (type.includes("spec") || type.includes("plan")) return FileText
  if (type.includes("qa") || type.includes("quality")) return Shield
  if (type.includes("step")) return Zap
  if (category === "execution") return Zap
  if (category === "planning") return FileText
  if (category === "discovery") return Search
  if (category === "qa") return Shield
  return Activity
}

function getEventColor(eventType: string): string {
  const type = eventType.toLowerCase()
  if (type.includes("completed") || type.includes("success")) return "text-green-600"
  if (type.includes("failed") || type.includes("error")) return "text-red-600"
  if (type.includes("warning") || type.includes("paused")) return "text-yellow-600"
  if (type.includes("started") || type.includes("running")) return "text-blue-600"
  return "text-muted-foreground"
}

function formatMetadataValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "number") {
    if (key.includes("duration") || key.includes("time")) {
      if (value < 1000) return `${value}ms`
      if (value < 60000) return `${(value / 1000).toFixed(1)}s`
      return `${(value / 60000).toFixed(1)}m`
    }
    if (key.includes("cost") || key.includes("price")) {
      return `$${value.toFixed(4)}`
    }
    if (key.includes("tokens")) {
      return value.toLocaleString()
    }
    return String(value)
  }
  if (typeof value === "string") {
    if (value.length > 100) return value.slice(0, 100) + "…"
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]"
    if (value.length <= 3) return value.join(", ")
    return `${value.slice(0, 3).join(", ")} +${value.length - 3} more`
  }
  return JSON.stringify(value)
}

function formatKeyLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function renderEventDetails(eventType: string, metadata: Record<string, unknown> | null | undefined) {
  if (!metadata || Object.keys(metadata).length === 0) return null

  const type = eventType.toLowerCase()
  const m = metadata as Record<string, unknown>

  if (type === "git_branch_created" || type === "git_branch_deleted") {
    const action = type === "git_branch_created" ? "Created" : "Deleted"
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{action} branch</span>
          <code className="bg-muted px-1.5 py-0.5 rounded text-xs">{String(m.branch)}</code>
          {m.base_ref && (
            <>
              <span className="text-muted-foreground">from</span>
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs">{String(m.base_ref)}</code>
            </>
          )}
        </div>
        <div className="flex gap-4 text-xs text-muted-foreground">
          {typeof m.push === "boolean" && <span>Push: {m.push ? "Yes" : "No"}</span>}
          {typeof m.checkout === "boolean" && <span>Checkout: {m.checkout ? "Yes" : "No"}</span>}
        </div>
      </div>
    )
  }

  if (type.includes("protocol_") || type.includes("step_")) {
    const details: Array<{ label: string; value: string }> = []
    if (m.status) details.push({ label: "Status", value: String(m.status) })
    if (m.duration_ms) details.push({ label: "Duration", value: formatMetadataValue("duration", m.duration_ms) })
    if (m.cost_tokens) details.push({ label: "Tokens", value: formatMetadataValue("tokens", m.cost_tokens) })
    if (m.cost_cents) details.push({ label: "Cost", value: `$${(Number(m.cost_cents) / 100).toFixed(4)}` })
    if (m.agent_id) details.push({ label: "Agent", value: String(m.agent_id) })
    if (m.engine_id) details.push({ label: "Engine", value: String(m.engine_id) })
    if (m.exit_code !== undefined) details.push({ label: "Exit Code", value: String(m.exit_code) })
    if (m.error) details.push({ label: "Error", value: String(m.error).slice(0, 100) })

    if (details.length === 0) return null

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-xs">
        {details.map(({ label, value }) => (
          <div key={label} className="flex gap-1">
            <span className="text-muted-foreground">{label}:</span>
            <span className="font-medium truncate">{value}</span>
          </div>
        ))}
      </div>
    )
  }

  if (type.includes("qa_") || type.includes("quality_")) {
    return (
      <div className="space-y-1">
        {m.gate_name && (
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{String(m.gate_name)}</span>
            {m.passed !== undefined && (
              <Badge variant={m.passed ? "default" : "destructive"} className="text-[10px]">
                {m.passed ? "Passed" : "Failed"}
              </Badge>
            )}
          </div>
        )}
        {m.findings && Array.isArray(m.findings) && m.findings.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {m.findings.length} finding(s)
          </div>
        )}
        {m.score !== undefined && (
          <div className="text-xs">
            Score: <span className="font-medium">{String(m.score)}</span>
          </div>
        )}
      </div>
    )
  }

  const importantKeys = ["status", "result", "count", "total", "name", "path", "reason", "message"]
  const displayKeys = Object.keys(m).filter(
    (k) => importantKeys.some((ik) => k.toLowerCase().includes(ik)) || importantKeys.includes(k.toLowerCase())
  )

  if (displayKeys.length > 0) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1 text-xs">
        {displayKeys.slice(0, 6).map((key) => (
          <div key={key} className="flex gap-1">
            <span className="text-muted-foreground">{formatKeyLabel(key)}:</span>
            <span className="font-medium truncate">{formatMetadataValue(key, m[key])}</span>
          </div>
        ))}
      </div>
    )
  }

  return null
}

function EventItem({ event: e }: { event: Event }) {
  const [showRaw, setShowRaw] = useState(false)
  const Icon = getEventIcon(e.event_type, e.event_category)
  const iconColor = getEventColor(e.event_type)
  const details = renderEventDetails(e.event_type, e.metadata)
  const hasMetadata = e.metadata && Object.keys(e.metadata).length > 0

  const timestamp = e.created_at ? new Date(e.created_at).toLocaleTimeString() : ""

  return (
    <div className="rounded-lg border p-3 hover:bg-muted/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className={cn("mt-0.5", iconColor)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="text-[10px] font-mono">
              {e.event_type}
            </Badge>
            {e.event_category && (
              <Badge variant="outline" className="text-[10px]">
                {e.event_category}
              </Badge>
            )}
            <div className="flex items-center gap-1 text-xs text-muted-foreground ml-auto">
              <Clock className="h-3 w-3" />
              <span>{timestamp}</span>
              <span className="mx-1">•</span>
              <span>{formatRelativeTime(e.created_at)}</span>
            </div>
          </div>

          <div className="text-sm font-medium">{e.message}</div>

          {details && <div className="pt-1">{details}</div>}

          <div className="flex flex-wrap items-center gap-3 text-xs">
            {typeof e.project_id === "number" && (
              <Link href={`/projects/${e.project_id}`} className="text-blue-600 hover:underline">
                {e.project_name ?? `Project #${e.project_id}`}
              </Link>
            )}
            {eventHasProtocolLink(e) && (
              <Link href={`/protocols/${e.protocol_run_id}`} className="text-blue-600 hover:underline">
                {e.protocol_name ?? `Protocol #${e.protocol_run_id}`}
              </Link>
            )}
            {typeof e.step_run_id === "number" && (
              <Link href={`/steps/${e.step_run_id}`} className="text-blue-600 hover:underline">
                Step #{e.step_run_id}
              </Link>
            )}
            <span className="text-muted-foreground font-mono">#{e.id}</span>
          </div>

          {hasMetadata && (
            <Collapsible open={showRaw} onOpenChange={setShowRaw}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground">
                  <ChevronDown className={cn("h-3 w-3 mr-1 transition-transform", showRaw && "rotate-180")} />
                  {showRaw ? "Hide" : "Show"} raw data
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <pre className="mt-2 text-xs bg-muted/40 rounded p-3 overflow-auto max-h-48">
                  {JSON.stringify(e.metadata, null, 2)}
                </pre>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      </div>
    </div>
  )
}

