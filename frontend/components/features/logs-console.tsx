"use client";

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, ChevronRight } from "lucide-react";

import {
  type ActivitySortOption,
  ActivityTable,
  MetadataSummary,
} from "@/components/features/activity-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JsonTree } from "@/components/ui/json-tree";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRecentLogs } from "@/lib/api/hooks/use-logs";
import type { AppLogEntry } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface LogsConsoleProps {
  mode?: "application" | "system";
  sourceFilter?: string;
}

const LOGS_TABLE_STORAGE_KEY = "devgodzilla_ops_logs_table_v1";

const levelBadgeClasses: Record<string, string> = {
  error: "bg-red-500/15 text-red-600 border-red-500/30",
  warning: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  warn: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  info: "bg-blue-500/15 text-blue-600 border-blue-500/30",
  debug: "bg-slate-500/15 text-slate-600 border-slate-500/30",
};

const levelPriority: Record<string, number> = {
  error: 4,
  warning: 3,
  warn: 3,
  info: 2,
  debug: 1,
};

const logSortOptions: ActivitySortOption<AppLogEntry>[] = [
  {
    value: "newest",
    label: "Newest first",
    pinLatest: true,
    compare: (a, b) => compareLogsByTimestamp(b, a),
  },
  {
    value: "oldest",
    label: "Oldest first",
    compare: (a, b) => compareLogsByTimestamp(a, b),
  },
  {
    value: "severity",
    label: "Severity",
    compare: (a, b) =>
      (levelPriority[b.level?.toLowerCase() ?? "info"] ?? 0) -
        (levelPriority[a.level?.toLowerCase() ?? "info"] ?? 0) ||
      compareLogsByTimestamp(b, a),
  },
  {
    value: "source",
    label: "Source",
    compare: (a, b) =>
      getSourceLabel(a).localeCompare(getSourceLabel(b), undefined, { sensitivity: "base" }) ||
      compareLogsByTimestamp(b, a),
  },
];

function compareLogsByTimestamp(a: AppLogEntry, b: AppLogEntry) {
  return getTimestampValue(a.timestamp) - getTimestampValue(b.timestamp) || a.id - b.id;
}

function getTimestampValue(value: string) {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function getSourceLabel(entry: AppLogEntry) {
  return entry.module || entry.logger_name || entry.source || "-";
}

function getSourceSecondary(entry: AppLogEntry) {
  const functionLabel = entry.funcName
    ? `${entry.funcName}${entry.lineno != null ? `:${entry.lineno}` : ""}`
    : entry.lineno != null
      ? `line ${entry.lineno}`
      : "";

  return [entry.logger_name && entry.logger_name !== getSourceLabel(entry) ? entry.logger_name : "", functionLabel]
    .filter(Boolean)
    .join(" · ");
}

function formatLogTime(timestamp: string) {
  const value = new Date(timestamp);
  if (Number.isNaN(value.getTime())) return timestamp;
  return value.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });
}

function formatLogDate(timestamp: string) {
  const value = new Date(timestamp);
  if (Number.isNaN(value.getTime())) return "";
  return value.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function LevelBadge({ level }: { level?: string | null }) {
  const normalized = level?.toLowerCase() ?? "info";
  return (
    <Badge
      variant="outline"
      className={cn(
        "min-w-16 justify-center font-mono text-[10px] uppercase",
        levelBadgeClasses[normalized] ?? levelBadgeClasses.info,
      )}
    >
      {normalized === "warning" ? "WARN" : normalized.toUpperCase()}
    </Badge>
  );
}

function LogDetails({ entry }: { entry: AppLogEntry }) {
  return (
    <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Context</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Timestamp</dt>
            <dd>{entry.timestamp}</dd>
            <dt className="text-muted-foreground">Level</dt>
            <dd>{entry.level}</dd>
            <dt className="text-muted-foreground">Source</dt>
            <dd>{entry.source}</dd>
            {entry.logger_name ? (
              <>
                <dt className="text-muted-foreground">Logger</dt>
                <dd>{entry.logger_name}</dd>
              </>
            ) : null}
            {entry.module ? (
              <>
                <dt className="text-muted-foreground">Module</dt>
                <dd>{entry.module}</dd>
              </>
            ) : null}
            {entry.funcName ? (
              <>
                <dt className="text-muted-foreground">Function</dt>
                <dd>{entry.funcName}</dd>
              </>
            ) : null}
            {entry.lineno != null ? (
              <>
                <dt className="text-muted-foreground">Line</dt>
                <dd>{entry.lineno}</dd>
              </>
            ) : null}
            {entry.thread ? (
              <>
                <dt className="text-muted-foreground">Thread</dt>
                <dd>{entry.thread}</dd>
              </>
            ) : null}
            {entry.process ? (
              <>
                <dt className="text-muted-foreground">Process</dt>
                <dd>{entry.process}</dd>
              </>
            ) : null}
            {entry.pathname ? (
              <>
                <dt className="text-muted-foreground">Path</dt>
                <dd className="break-all">{entry.pathname}</dd>
              </>
            ) : null}
          </dl>
        </div>
        <div>
          <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Message</p>
          <pre className="bg-muted/40 mt-2 overflow-x-auto rounded-md border p-3 text-xs whitespace-pre-wrap">
            {entry.message}
          </pre>
        </div>
      </div>

      <div>
        <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Metadata</p>
        <div className="mt-2">
          {entry.metadata && Object.keys(entry.metadata).length > 0 ? (
            <JsonTree value={entry.metadata} rootName="metadata" />
          ) : (
            <div className="text-muted-foreground rounded-md border border-dashed p-4 text-sm">
              No structured metadata.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function LogsConsole({ mode = "application", sourceFilter }: LogsConsoleProps) {
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const filters = useMemo(
    () => ({
      level: levelFilter === "all" ? undefined : levelFilter,
      source: sourceFilter,
      limit: 200,
    }),
    [levelFilter, sourceFilter],
  );

  const { data: logs, isLoading } = useRecentLogs(filters);

  const columns = useMemo<ColumnDef<AppLogEntry>[]>(
    () => [
      {
        id: "details",
        header: "",
        enableSorting: false,
        cell: ({ row }) => {
          const entry = row.original;
          const isExpanded = expandedIds.has(entry.id);
          return (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(event) => {
                event.stopPropagation();
                setExpandedIds((current) => {
                  const next = new Set(current);
                  if (next.has(entry.id)) next.delete(entry.id);
                  else next.add(entry.id);
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
        id: "timestamp",
        header: "Time",
        accessorKey: "timestamp",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="min-w-[7rem]">
            <div className="font-mono">{formatLogTime(row.original.timestamp)}</div>
            <div className="text-muted-foreground text-[11px]">
              {formatLogDate(row.original.timestamp)} · {formatRelativeTime(row.original.timestamp)}
            </div>
          </div>
        ),
      },
      {
        id: "level",
        header: "Level",
        accessorKey: "level",
        enableSorting: false,
        cell: ({ row }) => <LevelBadge level={row.original.level} />,
      },
      {
        id: "source",
        header: "Source",
        accessorKey: "source",
        enableSorting: false,
        cell: ({ row }) => {
          const entry = row.original;
          const secondary = getSourceSecondary(entry);
          return (
            <div className="min-w-[14rem] max-w-[18rem]">
              <div className="truncate font-medium" title={getSourceLabel(entry)}>
                {getSourceLabel(entry)}
              </div>
              <div className="text-muted-foreground truncate text-[11px]" title={secondary || entry.source}>
                {secondary || entry.source}
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
        accessorFn: (entry) => JSON.stringify(entry.metadata ?? {}),
        enableSorting: false,
        cell: ({ row }) => <MetadataSummary metadata={row.original.metadata} />,
      },
    ],
    [expandedIds],
  );

  const searchAccessor = (entry: AppLogEntry) =>
    [
      entry.timestamp,
      entry.level,
      entry.source,
      entry.logger_name,
      entry.module,
      entry.funcName,
      entry.pathname,
      entry.thread,
      entry.process,
      entry.message,
      JSON.stringify(entry.metadata ?? {}),
    ]
      .filter(Boolean)
      .join(" ");

  const filterControls = (
    <>
      <Select value={levelFilter} onValueChange={setLevelFilter}>
        <SelectTrigger className="h-8 w-[140px]">
          <SelectValue placeholder="Level" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All levels</SelectItem>
          <SelectItem value="error">Error</SelectItem>
          <SelectItem value="warning">Warning</SelectItem>
          <SelectItem value="info">Info</SelectItem>
          <SelectItem value="debug">Debug</SelectItem>
        </SelectContent>
      </Select>
      <Badge variant="outline" className="text-[10px]">
        {mode === "system" ? "System logs" : "Application logs"}
      </Badge>
      {sourceFilter ? (
        <Badge variant="outline" className="max-w-[20rem] truncate text-[10px]" title={sourceFilter}>
          Source: {sourceFilter}
        </Badge>
      ) : null}
    </>
  );

  return (
    <ActivityTable
      data={logs}
      columns={columns}
      getRowId={(entry) => String(entry.id)}
      sortOptions={logSortOptions}
      defaultSortValue="newest"
      storageKey={
        LOGS_TABLE_STORAGE_KEY +
        (sourceFilter ? `_${sourceFilter.replace(/[^a-z0-9_-]/gi, "_")}` : "")
      }
      searchPlaceholder="Search logs, sources, functions, or metadata..."
      searchAccessor={searchAccessor}
      itemLabel="log entries"
      filterControls={filterControls}
      statusContent={
        <Badge variant="outline" className="text-[10px]">
          Polling every 5s
        </Badge>
      }
      isLoading={isLoading}
      emptyState={{
        icon: Activity,
        title: "No logs",
        description: "No log entries match the current filters.",
      }}
      isRowExpanded={(entry) => expandedIds.has(entry.id)}
      renderExpandedContent={(entry) => <LogDetails entry={entry} />}
      emptyMessage="No log entries match the current search or filters."
    />
  );
}
