"use client";

import { useEffect, useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, ChevronRight, RefreshCw } from "lucide-react";

import {
  type ActivitySortOption,
  ActivityTable,
  MetadataSummary,
} from "@/components/features/activity-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { JsonTree } from "@/components/ui/json-tree";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjects, useRecentEvents } from "@/lib/api";
import type { Event, EventFilters } from "@/lib/api/types";
import { formatRelativeTime, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { renderStructuredMetadata } from "@/lib/utils/event-metadata";
import { useWebSocketEvent } from "@/lib/websocket/hooks";

const eventTypeColors: Record<string, string> = {
  onboarding_enqueued: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  onboarding_enqueue_failed: "text-destructive border-destructive/30 bg-destructive/10",
  onboarding_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  onboarding_repo_ready: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  onboarding_speckit_initialized: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  onboarding_failed: "text-destructive border-destructive/30 bg-destructive/10",
  discovery_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  discovery_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  discovery_failed: "text-destructive border-destructive/30 bg-destructive/10",
  discovery_skipped: "text-muted-foreground border-border bg-muted/40",
  step_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  step_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  step_failed: "text-destructive border-destructive/30 bg-destructive/10",
  step_qa_required: "text-amber-600 border-amber-500/30 bg-amber-500/10",
  qa_started: "text-amber-600 border-amber-500/30 bg-amber-500/10",
  qa_passed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  qa_failed: "text-destructive border-destructive/30 bg-destructive/10",
  planning_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  planning_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  protocol_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  protocol_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  protocol_failed: "text-destructive border-destructive/30 bg-destructive/10",
  protocol_paused: "text-amber-600 border-amber-500/30 bg-amber-500/10",
  protocol_resumed: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  policy_finding: "text-orange-600 border-orange-500/30 bg-orange-500/10",
  speckit_specify_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  speckit_specify_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  speckit_specify_failed: "text-destructive border-destructive/30 bg-destructive/10",
  speckit_plan_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  speckit_plan_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  speckit_plan_failed: "text-destructive border-destructive/30 bg-destructive/10",
  speckit_tasks_started: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  speckit_tasks_completed: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  speckit_tasks_failed: "text-destructive border-destructive/30 bg-destructive/10",
  ci_webhook_github_workflow_run: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
  ci_webhook_github_check_run: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
  ci_webhook_github_pull_request: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
  ci_webhook_gitlab_pipeline: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
  ci_webhook_gitlab_merge_request: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
};

const categoryLabels: Record<string, string> = {
  onboarding: "Onboarding",
  discovery: "Discovery",
  planning: "Planning",
  execution: "Execution",
  qa: "QA",
  policy: "Policy",
  speckit: "SpecKit",
  ci_webhook: "CI/Webhook",
  feedback: "Feedback",
  clarification: "Clarification",
  other: "Other",
};

const categoryColors: Record<string, string> = {
  onboarding: "text-sky-600 border-sky-500/30 bg-sky-500/10",
  discovery: "text-indigo-600 border-indigo-500/30 bg-indigo-500/10",
  planning: "text-blue-600 border-blue-500/30 bg-blue-500/10",
  execution: "text-emerald-600 border-emerald-500/30 bg-emerald-500/10",
  qa: "text-amber-600 border-amber-500/30 bg-amber-500/10",
  policy: "text-orange-600 border-orange-500/30 bg-orange-500/10",
  speckit: "text-cyan-600 border-cyan-500/30 bg-cyan-500/10",
  ci_webhook: "text-fuchsia-600 border-fuchsia-500/30 bg-fuchsia-500/10",
  feedback: "text-pink-600 border-pink-500/30 bg-pink-500/10",
  clarification: "text-teal-600 border-teal-500/30 bg-teal-500/10",
  other: "text-muted-foreground border-border bg-muted/40",
};

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
];

const categoryOptions = [
  "onboarding",
  "discovery",
  "planning",
  "execution",
  "qa",
  "policy",
  "speckit",
  "ci_webhook",
  "feedback",
  "clarification",
  "other",
];

const PRESETS_STORAGE_KEY = "devgodzilla_ops_events_presets_v1";
const SETTINGS_STORAGE_KEY = "devgodzilla_ops_events_settings_v1";
const EVENTS_TABLE_STORAGE_KEY = "devgodzilla_ops_events_table_v1";
const DEFAULT_REFRESH_MS = 10000;

const eventSortOptions: ActivitySortOption<Event>[] = [
  {
    value: "newest",
    label: "Newest first",
    pinLatest: true,
    compare: (a, b) => compareEventsByCreatedAt(b, a),
  },
  {
    value: "oldest",
    label: "Oldest first",
    compare: (a, b) => compareEventsByCreatedAt(a, b),
  },
  {
    value: "event_type",
    label: "Event type",
    compare: (a, b) =>
      a.event_type.localeCompare(b.event_type, undefined, { sensitivity: "base" }) ||
      compareEventsByCreatedAt(b, a),
  },
  {
    value: "project",
    label: "Project",
    compare: (a, b) =>
      (a.project_name || "").localeCompare(b.project_name || "", undefined, { sensitivity: "base" }) ||
      compareEventsByCreatedAt(b, a),
  },
  {
    value: "category",
    label: "Category",
    compare: (a, b) =>
      (a.event_category || "other").localeCompare(b.event_category || "other", undefined, { sensitivity: "base" }) ||
      compareEventsByCreatedAt(b, a),
  },
];

function compareEventsByCreatedAt(a: Event, b: Event) {
  return getDateValue(a.created_at) - getDateValue(b.created_at) || a.id - b.id;
}

function getDateValue(value: string) {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatEventDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function EventDetails({ event }: { event: Event }) {
  return (
    <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Context</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Created</dt>
            <dd>{event.created_at}</dd>
            <dt className="text-muted-foreground">Type</dt>
            <dd>{event.event_type}</dd>
            <dt className="text-muted-foreground">Category</dt>
            <dd>{categoryLabels[event.event_category || "other"] ?? event.event_category ?? "Other"}</dd>
            {event.project_name ? (
              <>
                <dt className="text-muted-foreground">Project</dt>
                <dd>{event.project_name}</dd>
              </>
            ) : null}
            {event.protocol_name ? (
              <>
                <dt className="text-muted-foreground">Protocol</dt>
                <dd>{event.protocol_name}</dd>
              </>
            ) : null}
            {event.protocol_run_id != null ? (
              <>
                <dt className="text-muted-foreground">Protocol run</dt>
                <dd>{event.protocol_run_id}</dd>
              </>
            ) : null}
            {event.step_run_id != null ? (
              <>
                <dt className="text-muted-foreground">Step run</dt>
                <dd>{event.step_run_id}</dd>
              </>
            ) : null}
            {event.spec_run_id != null ? (
              <>
                <dt className="text-muted-foreground">Spec run</dt>
                <dd>{event.spec_run_id}</dd>
              </>
            ) : null}
          </dl>
        </div>
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Message</p>
          <pre className="bg-muted/40 mt-2 overflow-x-auto rounded-md border p-3 text-xs whitespace-pre-wrap">
            {event.message}
          </pre>
        </div>
      </div>
      <div className="space-y-3">
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Structured details</p>
          <div className="mt-2">{renderStructuredMetadata(event.metadata)}</div>
        </div>
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Raw metadata</p>
          <div className="mt-2">
            {event.metadata && Object.keys(event.metadata).length > 0 ? (
              <JsonTree value={event.metadata} rootName="metadata" />
            ) : (
              <div className="text-muted-foreground rounded-md border border-dashed p-4 text-sm">
                No structured metadata.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function EventsPage() {
  const [filters, setFilters] = useState<EventFilters>({ limit: 50, categories: [] });
  const [presetName, setPresetName] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string>("");
  const [expandedEventIds, setExpandedEventIds] = useState<Set<number>>(new Set());
  const [presets, setPresets] = useState<Array<{ name: string; filters: EventFilters }>>(() => {
    if (typeof window === "undefined") return [];
    try {
      const stored = localStorage.getItem(PRESETS_STORAGE_KEY);
      if (!stored) return [];
      const parsed = JSON.parse(stored) as Array<{ name: string; filters: EventFilters }>;
      return Array.isArray(parsed) ? parsed.filter((preset) => preset?.name) : [];
    } catch {
      return [];
    }
  });
  const [refreshIntervalMs, setRefreshIntervalMs] = useState<number>(() => {
    if (typeof window === "undefined") return DEFAULT_REFRESH_MS;
    try {
      const stored = localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (!stored) return DEFAULT_REFRESH_MS;
      const parsed = JSON.parse(stored) as { refreshIntervalMs?: number };
      return typeof parsed.refreshIntervalMs === "number"
        ? parsed.refreshIntervalMs
        : DEFAULT_REFRESH_MS;
    } catch {
      return DEFAULT_REFRESH_MS;
    }
  });

  const {
    data: events,
    isLoading,
    refetch,
  } = useRecentEvents(filters, { refetchIntervalMs: refreshIntervalMs });
  const { data: projects } = useProjects();

  useWebSocketEvent("events", [], ["ops", "recentEvents"]);

  const selectedProject = useMemo(
    () => projects?.find((project) => project.id === filters.project_id),
    [filters.project_id, projects],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ refreshIntervalMs }));
  }, [refreshIntervalMs]);

  const toggleCategory = (category: string) => {
    setFilters((current) => {
      const next = new Set(current.categories ?? []);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return { ...current, categories: Array.from(next).sort() };
    });
  };

  const persistPresets = (nextPresets: Array<{ name: string; filters: EventFilters }>) => {
    setPresets(nextPresets);
    if (typeof window !== "undefined") {
      localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(nextPresets));
    }
  };

  const normalizeFilters = (value: EventFilters): EventFilters => ({
    project_id: typeof value.project_id === "number" ? value.project_id : undefined,
    protocol_run_id: typeof value.protocol_run_id === "number" ? value.protocol_run_id : undefined,
    event_type: typeof value.event_type === "string" ? value.event_type : undefined,
    categories: Array.isArray(value.categories) ? value.categories.filter(Boolean).sort() : [],
    limit: typeof value.limit === "number" ? value.limit : 50,
  });

  const handleSavePreset = () => {
    const name = presetName.trim();
    if (!name) return;
    const normalized = normalizeFilters(filters);
    const updated = presets.filter((preset) => preset.name !== name);
    updated.unshift({ name, filters: normalized });
    persistPresets(updated.slice(0, 20));
    setSelectedPreset(name);
  };

  const handleApplyPreset = (name: string) => {
    if (name === "none") {
      setSelectedPreset("");
      return;
    }
    setSelectedPreset(name);
    const preset = presets.find((item) => item.name === name);
    if (preset) {
      setFilters(normalizeFilters(preset.filters));
      setPresetName(preset.name);
    }
  };

  const handleDeletePreset = () => {
    if (!selectedPreset) return;
    const updated = presets.filter((preset) => preset.name !== selectedPreset);
    persistPresets(updated);
    setSelectedPreset("");
  };

  const resetFilters = () => {
    setFilters({ limit: 50, categories: [] });
    setSelectedPreset("");
    setPresetName("");
    setExpandedEventIds(new Set());
  };

  const columns = useMemo<ColumnDef<Event>[]>(
    () => [
      {
        id: "details",
        header: "",
        enableSorting: false,
        cell: ({ row }) => {
          const event = row.original;
          const isExpanded = expandedEventIds.has(event.id);
          return (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(clickEvent) => {
                clickEvent.stopPropagation();
                setExpandedEventIds((current) => {
                  const next = new Set(current);
                  if (next.has(event.id)) next.delete(event.id);
                  else next.add(event.id);
                  return next;
                });
              }}
            >
              <ChevronRight className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-90")} />
            </Button>
          );
        },
      },
      {
        id: "created_at",
        header: "Time",
        accessorKey: "created_at",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="min-w-[7rem]">
            <div className="font-mono">{formatTime(row.original.created_at)}</div>
            <div className="text-muted-foreground text-[11px]">
              {formatEventDate(row.original.created_at)} · {formatRelativeTime(row.original.created_at)}
            </div>
          </div>
        ),
      },
      {
        id: "event_type",
        header: "Event",
        accessorKey: "event_type",
        enableSorting: false,
        cell: ({ row }) => (
          <Badge
            variant="outline"
            className={cn(
              "max-w-[18rem] truncate font-mono text-[10px]",
              eventTypeColors[row.original.event_type] || "text-foreground border-border bg-muted/30",
            )}
            title={row.original.event_type}
          >
            {row.original.event_type}
          </Badge>
        ),
      },
      {
        id: "category",
        header: "Category",
        accessorFn: (event) => event.event_category || "other",
        enableSorting: false,
        cell: ({ row }) => {
          const category = row.original.event_category || "other";
          return (
            <Badge
              variant="outline"
              className={cn("text-[10px]", categoryColors[category] || categoryColors.other)}
            >
              {categoryLabels[category] ?? category}
            </Badge>
          );
        },
      },
      {
        id: "scope",
        header: "Scope",
        accessorFn: (event) => `${event.project_name || ""} ${event.protocol_name || ""}`,
        enableSorting: false,
        cell: ({ row }) => {
          const event = row.original;
          return (
            <div className="min-w-[14rem] max-w-[18rem]">
              <div className="truncate font-medium" title={event.project_name || "-"}>
                {event.project_name || "-"}
              </div>
              <div className="text-muted-foreground truncate text-[11px]" title={event.protocol_name || ""}>
                {event.protocol_name || (event.protocol_run_id != null ? `Run ${event.protocol_run_id}` : "No protocol")}
              </div>
            </div>
          );
        },
      },
      {
        id: "message",
        header: "Message",
        accessorKey: "message",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="min-w-[20rem] max-w-[48rem]">
            <div className="line-clamp-2 break-words" title={row.original.message}>
              {row.original.message}
            </div>
          </div>
        ),
      },
      {
        id: "metadata",
        header: "Metadata",
        accessorFn: (event) => JSON.stringify(event.metadata ?? {}),
        enableSorting: false,
        cell: ({ row }) => <MetadataSummary metadata={row.original.metadata} />,
      },
    ],
    [expandedEventIds],
  );

  const tableFilterSummary = (
    <>
      {selectedProject ? (
        <Badge variant="outline" className="text-[10px]">
          Project: {selectedProject.name}
        </Badge>
      ) : null}
      {filters.event_type ? (
        <Badge variant="outline" className="max-w-[18rem] truncate text-[10px]" title={filters.event_type}>
          Type: {filters.event_type}
        </Badge>
      ) : null}
      {(filters.categories?.length ?? 0) > 0 ? (
        <Badge variant="outline" className="text-[10px]">
          {filters.categories?.length} categories
        </Badge>
      ) : null}
      <Badge variant="outline" className="text-[10px]">
        Limit: {filters.limit || 50}
      </Badge>
    </>
  );

  const searchAccessor = (event: Event) =>
    [
      event.created_at,
      event.event_type,
      event.event_category,
      event.project_name,
      event.protocol_name,
      event.protocol_run_id,
      event.step_run_id,
      event.spec_run_id,
      event.message,
      JSON.stringify(event.metadata ?? {}),
    ]
      .filter(Boolean)
      .join(" ");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Events</h2>
          <p className="text-muted-foreground text-sm">
            Newest-first activity stream with inline context and sortable views.
          </p>
        </div>
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
          onChange={(event) => setPresetName(event.target.value)}
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
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              project_id: value === "all" ? undefined : Number(value),
            }))
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
          onValueChange={(value) =>
            setFilters((current) => ({ ...current, event_type: value === "all" ? undefined : value }))
          }
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
          onChange={(event) =>
            setFilters((current) => ({ ...current, limit: Number(event.target.value) || 50 }))
          }
        />

        <Select value={String(refreshIntervalMs)} onValueChange={(value) => setRefreshIntervalMs(Number(value))}>
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
          const selected = filters.categories?.includes(category);
          return (
            <Button
              key={category}
              variant={selected ? "secondary" : "outline"}
              size="sm"
              onClick={() => toggleCategory(category)}
            >
              {categoryLabels[category] ?? category}
            </Button>
          );
        })}
      </div>

      <ActivityTable
        data={events}
        columns={columns}
        getRowId={(event) => String(event.id)}
        sortOptions={eventSortOptions}
        defaultSortValue="newest"
        storageKey={EVENTS_TABLE_STORAGE_KEY}
        searchPlaceholder="Search events, projects, protocols, messages, or metadata..."
        searchAccessor={searchAccessor}
        itemLabel="events"
        filterControls={tableFilterSummary}
        statusContent={
          <Badge variant="outline" className="text-[10px]">
            Refresh: {refreshIntervalMs === 0 ? "Manual" : `${refreshIntervalMs / 1000}s`}
          </Badge>
        }
        isLoading={isLoading}
        emptyState={{
          icon: Activity,
          title: "No events",
          description: "No events match the current filter criteria.",
        }}
        isRowExpanded={(event) => expandedEventIds.has(event.id)}
        renderExpandedContent={(event) => <EventDetails event={event} />}
        emptyMessage="No events match the current search or filters."
      />
    </div>
  );
}
