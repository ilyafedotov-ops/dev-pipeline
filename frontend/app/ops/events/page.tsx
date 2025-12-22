"use client"

import { useEffect, useState } from "react"
import { useRecentEvents, useProjects } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { RefreshCw, Activity } from "lucide-react"
import { formatTime, formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { EventFilters } from "@/lib/api/types"

const eventTypeColors: Record<string, string> = {
  onboarding_enqueued: "text-blue-500",
  onboarding_enqueue_failed: "text-destructive",
  onboarding_started: "text-blue-500",
  onboarding_repo_ready: "text-green-500",
  onboarding_speckit_initialized: "text-green-500",
  onboarding_failed: "text-destructive",
  discovery_started: "text-blue-500",
  discovery_completed: "text-green-500",
  discovery_failed: "text-destructive",
  discovery_skipped: "text-muted-foreground",
  step_started: "text-blue-500",
  step_completed: "text-green-500",
  step_failed: "text-destructive",
  step_qa_required: "text-yellow-500",
  qa_started: "text-yellow-500",
  qa_passed: "text-green-500",
  qa_failed: "text-destructive",
  planning_started: "text-blue-500",
  planning_completed: "text-green-500",
  protocol_started: "text-blue-500",
  protocol_completed: "text-green-500",
  protocol_failed: "text-destructive",
  protocol_paused: "text-yellow-500",
  protocol_resumed: "text-blue-500",
  policy_finding: "text-yellow-500",
  // SpecKit events
  speckit_specify_started: "text-blue-500",
  speckit_specify_completed: "text-green-500",
  speckit_specify_failed: "text-destructive",
  speckit_plan_started: "text-blue-500",
  speckit_plan_completed: "text-green-500",
  speckit_plan_failed: "text-destructive",
  speckit_tasks_started: "text-blue-500",
  speckit_tasks_completed: "text-green-500",
  speckit_tasks_failed: "text-destructive",
  // CI Webhooks
  ci_webhook_github_workflow_run: "text-purple-500",
  ci_webhook_github_check_run: "text-purple-500",
  ci_webhook_github_pull_request: "text-purple-500",
  ci_webhook_gitlab_pipeline: "text-purple-500",
  ci_webhook_gitlab_merge_request: "text-purple-500",
}

const categoryLabels: Record<string, string> = {
  onboarding: "Onboarding",
  discovery: "Discovery",
  planning: "Planning",
  execution: "Execution",
  qa: "QA",
  policy: "Policy",
  speckit: "SpecKit",
  ci_webhook: "CI/Webhook",
  other: "Other",
}

const categoryColors: Record<string, string> = {
  onboarding: "text-sky-500",
  discovery: "text-indigo-500",
  planning: "text-blue-500",
  execution: "text-emerald-500",
  qa: "text-amber-500",
  policy: "text-orange-500",
  speckit: "text-cyan-500",
  ci_webhook: "text-fuchsia-500",
  other: "text-muted-foreground",
}

const eventTypeOptions = [
  "onboarding_enqueued",
  "onboarding_enqueue_failed",
  "onboarding_started",
  "onboarding_repo_ready",
  "onboarding_speckit_initialized",
  "onboarding_failed",
  "discovery_started",
  "discovery_completed",
  "discovery_failed",
  "discovery_skipped",
  "protocol_started",
  "protocol_completed",
  "protocol_failed",
  "protocol_paused",
  "protocol_resumed",
  "planning_started",
  "planning_completed",
  "step_started",
  "step_completed",
  "step_failed",
  "step_qa_required",
  "qa_started",
  "qa_passed",
  "qa_failed",
  "policy_finding",
  "speckit_specify_started",
  "speckit_specify_completed",
  "speckit_specify_failed",
  "speckit_plan_started",
  "speckit_plan_completed",
  "speckit_plan_failed",
  "speckit_tasks_started",
  "speckit_tasks_completed",
  "speckit_tasks_failed",
  "ci_webhook_github_workflow_run",
  "ci_webhook_github_check_run",
  "ci_webhook_github_pull_request",
  "ci_webhook_gitlab_pipeline",
  "ci_webhook_gitlab_merge_request",
]

const categoryOptions = [
  "onboarding",
  "discovery",
  "planning",
  "execution",
  "qa",
  "policy",
  "speckit",
  "ci_webhook",
  "other",
]

const PRESETS_STORAGE_KEY = "devgodzilla_ops_events_presets_v1"
const SETTINGS_STORAGE_KEY = "devgodzilla_ops_events_settings_v1"
const DEFAULT_REFRESH_MS = 10000

export default function EventsPage() {
  const [filters, setFilters] = useState<EventFilters>({ limit: 50, categories: [] })
  const [presetName, setPresetName] = useState("")
  const [selectedPreset, setSelectedPreset] = useState<string>("")
  const [expandedEventIds, setExpandedEventIds] = useState<Set<number>>(new Set())
  const [presets, setPresets] = useState<Array<{ name: string; filters: EventFilters }>>(() => {
    if (typeof window === "undefined") return []
    try {
      const stored = localStorage.getItem(PRESETS_STORAGE_KEY)
      if (!stored) return []
      const parsed = JSON.parse(stored) as Array<{ name: string; filters: EventFilters }>
      return Array.isArray(parsed) ? parsed.filter((preset) => preset?.name) : []
    } catch {
      return []
    }
  })
  const [refreshIntervalMs, setRefreshIntervalMs] = useState<number>(() => {
    if (typeof window === "undefined") return DEFAULT_REFRESH_MS
    try {
      const stored = localStorage.getItem(SETTINGS_STORAGE_KEY)
      if (!stored) return DEFAULT_REFRESH_MS
      const parsed = JSON.parse(stored) as { refreshIntervalMs?: number }
      return typeof parsed.refreshIntervalMs === "number" ? parsed.refreshIntervalMs : DEFAULT_REFRESH_MS
    } catch {
      return DEFAULT_REFRESH_MS
    }
  })

  const { data: events, isLoading, refetch } = useRecentEvents(filters, { refetchIntervalMs: refreshIntervalMs })
  const { data: projects } = useProjects()

  useEffect(() => {
    if (typeof window === "undefined") return
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ refreshIntervalMs }))
  }, [refreshIntervalMs])

  const toggleCategory = (category: string) => {
    setFilters((current) => {
      const next = new Set(current.categories ?? [])
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return { ...current, categories: Array.from(next).sort() }
    })
  }

  const toggleEventDetails = (eventId: number) => {
    setExpandedEventIds((current) => {
      const next = new Set(current)
      if (next.has(eventId)) {
        next.delete(eventId)
      } else {
        next.add(eventId)
      }
      return next
    })
  }

  const persistPresets = (nextPresets: Array<{ name: string; filters: EventFilters }>) => {
    setPresets(nextPresets)
    if (typeof window !== "undefined") {
      localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(nextPresets))
    }
  }

  const normalizeFilters = (value: EventFilters): EventFilters => ({
    project_id: typeof value.project_id === "number" ? value.project_id : undefined,
    protocol_run_id: typeof value.protocol_run_id === "number" ? value.protocol_run_id : undefined,
    event_type: typeof value.event_type === "string" ? value.event_type : undefined,
    categories: Array.isArray(value.categories) ? value.categories.filter(Boolean).sort() : [],
    limit: typeof value.limit === "number" ? value.limit : 50,
  })

  const handleSavePreset = () => {
    const name = presetName.trim()
    if (!name) return
    const normalized = normalizeFilters(filters)
    const updated = presets.filter((preset) => preset.name !== name)
    updated.unshift({ name, filters: normalized })
    persistPresets(updated.slice(0, 20))
    setSelectedPreset(name)
  }

  const handleApplyPreset = (name: string) => {
    if (name === "none") {
      setSelectedPreset("")
      return
    }
    setSelectedPreset(name)
    const preset = presets.find((item) => item.name === name)
    if (preset) {
      setFilters(normalizeFilters(preset.filters))
      setPresetName(preset.name)
    }
  }

  const handleDeletePreset = () => {
    if (!selectedPreset) return
    const updated = presets.filter((preset) => preset.name !== selectedPreset)
    persistPresets(updated)
    setSelectedPreset("")
  }

  const resetFilters = () => {
    setFilters({ limit: 50, categories: [] })
    setSelectedPreset("")
    setPresetName("")
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Events</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="ghost" onClick={resetFilters}>
            Reset Filters
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={selectedPreset || "none"} onValueChange={handleApplyPreset}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Presets" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Presets</SelectItem>
            {presets.map((preset) => (
              <SelectItem key={preset.name} value={preset.name}>
                {preset.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          placeholder="Preset name"
          value={presetName}
          onChange={(e) => setPresetName(e.target.value)}
          className="w-48"
        />
        <Button variant="outline" onClick={handleSavePreset}>
          Save Preset
        </Button>
        <Button variant="ghost" onClick={handleDeletePreset} disabled={!selectedPreset}>
          Delete
        </Button>
      </div>

      <div className="flex flex-wrap gap-4">
        <Select
          value={filters.project_id?.toString() || "all"}
          onValueChange={(v) =>
            setFilters((f) => ({ ...f, project_id: v === "all" ? undefined : Number(v) }))
          }
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All Projects" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Projects</SelectItem>
            {projects?.map((project) => (
              <SelectItem key={project.id} value={project.id.toString()}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.event_type || "all"}
          onValueChange={(v) => setFilters((f) => ({ ...f, event_type: v === "all" ? undefined : v }))}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Event Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {eventTypeOptions.map((eventType) => (
              <SelectItem key={eventType} value={eventType}>
                {eventType}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="number"
          placeholder="Limit"
          className="w-24"
          value={filters.limit || 50}
          onChange={(e) => setFilters((f) => ({ ...f, limit: Number(e.target.value) || 50 }))}
        />

        <Select value={String(refreshIntervalMs)} onValueChange={(v) => setRefreshIntervalMs(Number(v))}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Refresh" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Manual</SelectItem>
            <SelectItem value="5000">5s</SelectItem>
            <SelectItem value="10000">10s</SelectItem>
            <SelectItem value="30000">30s</SelectItem>
            <SelectItem value="60000">60s</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-wrap gap-2">
        {categoryOptions.map((category) => {
          const selected = filters.categories?.includes(category)
          return (
            <Button
              key={category}
              variant={selected ? "secondary" : "outline"}
              size="sm"
              onClick={() => toggleCategory(category)}
            >
              {categoryLabels[category] ?? category}
            </Button>
          )
        })}
      </div>

      {isLoading ? (
        <LoadingState message="Loading events..." />
      ) : !events || events.length === 0 ? (
        <EmptyState icon={Activity} title="No events" description="No events match your filter criteria." />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Event Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {events.map((event) => {
                const category = event.event_category || "other"
                const color =
                  eventTypeColors[event.event_type] || categoryColors[category] || "text-muted-foreground"
                const hasMetadata = event.metadata && Object.keys(event.metadata).length > 0
                const isExpanded = expandedEventIds.has(event.id)

                return (
                  <div key={event.id} className="flex gap-4 items-start">
                    <div className="text-sm text-muted-foreground min-w-24 font-mono">
                      {formatTime(event.created_at)}
                    </div>
                    <div className="relative flex-shrink-0">
                      <div className="h-3 w-3 rounded-full bg-muted border-2 border-background" />
                      <div className="absolute top-3 bottom-0 left-1/2 -translate-x-1/2 w-px bg-border h-full" />
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn("font-mono text-sm", color)}>{event.event_type}</span>
                        <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                          {categoryLabels[category] ?? category}
                        </span>
                        {event.project_name && (
                          <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                            {event.project_name}
                          </span>
                        )}
                        {event.protocol_name && (
                          <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                            {event.protocol_name}
                          </span>
                        )}
                        {hasMetadata && (
                          <button
                            type="button"
                            onClick={() => toggleEventDetails(event.id)}
                            className="text-xs text-muted-foreground hover:text-foreground"
                          >
                            {isExpanded ? "Hide details" : "Details"}
                          </button>
                        )}
                      </div>
                      <p className="text-sm mt-1">{event.message}</p>
                      <p className="text-xs text-muted-foreground mt-1">{formatRelativeTime(event.created_at)}</p>
                      {hasMetadata && isExpanded && (
                        <pre className="mt-3 text-xs bg-muted rounded p-3 whitespace-pre-wrap break-words">
                          {JSON.stringify(event.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
