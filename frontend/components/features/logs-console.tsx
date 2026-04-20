"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Activity } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRecentLogs } from "@/lib/api/hooks/use-logs";
import type { AppLogEntry, LogLevel } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export interface LogsConsoleProps {
  mode?: "application" | "system";
  sourceFilter?: string;
}

const levelColors: Record<string, string> = {
  error: "text-red-500 bg-red-500/10",
  warning: "text-yellow-500 bg-yellow-500/10",
  warn: "text-yellow-500 bg-yellow-500/10",
  info: "text-blue-500 bg-blue-500/10",
  debug: "text-gray-400 bg-gray-400/10",
};

const levelBadgeColors: Record<string, string> = {
  error: "bg-red-500/15 text-red-500 border-red-500/30",
  warning: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30",
  warn: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30",
  info: "bg-blue-500/15 text-blue-500 border-blue-500/30",
  debug: "bg-gray-500/15 text-gray-400 border-gray-500/30",
};

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    });
  } catch {
    return ts;
  }
}

function LogEntryRow({ entry, isExpanded, onToggle }: {
  entry: AppLogEntry;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const level = entry.level?.toLowerCase() ?? "info";
  const colorClass = levelColors[level] ?? levelColors.info;
  const badgeClass = levelBadgeColors[level] ?? levelBadgeColors.info;

  // Extract source: prefer module, then logger_name, then source
  const source = entry.module || entry.logger_name || entry.source || "—";
  const hasExpandable = (entry.funcName || entry.lineno || entry.metadata) ? true : false;

  return (
    <div
      className={cn(
        "hover:bg-muted/40 cursor-pointer border-b border-border/30 px-3 py-1.5 font-mono text-xs transition-colors last:border-b-0",
        level === "error" && "bg-red-500/5",
      )}
      onClick={hasExpandable ? onToggle : undefined}
    >
      <div className="flex items-start gap-3">
        {/* Timestamp */}
        <span className="text-muted-foreground min-w-20 shrink-0">
          {formatTimestamp(entry.timestamp)}
        </span>

        {/* Level badge */}
        <span
          className={cn(
            "inline-flex min-w-14 shrink-0 items-center justify-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase",
            badgeClass,
          )}
        >
          {level === "warning" ? "WARN" : level.toUpperCase()}
        </span>

        {/* Source / module */}
        <span className="text-muted-foreground min-w-32 shrink-0 truncate">
          {source}
        </span>

        {/* Message */}
        <span className={cn("min-w-0 flex-1 break-words", colorClass)}>
          {entry.message}
        </span>
      </div>

      {/* Expandable metadata */}
      {isExpanded && (
        <div className="bg-muted/30 mt-1.5 rounded p-2">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-3">
            {entry.funcName && (
              <div>
                <span className="text-muted-foreground">funcName:</span>{" "}
                <span className="font-medium">{entry.funcName}</span>
              </div>
            )}
            {entry.lineno != null && (
              <div>
                <span className="text-muted-foreground">lineno:</span>{" "}
                <span className="font-medium">{entry.lineno}</span>
              </div>
            )}
            {entry.module && (
              <div>
                <span className="text-muted-foreground">module:</span>{" "}
                <span className="font-medium">{entry.module}</span>
              </div>
            )}
            {entry.logger_name && (
              <div>
                <span className="text-muted-foreground">logger:</span>{" "}
                <span className="font-medium">{entry.logger_name}</span>
              </div>
            )}
            {entry.thread && (
              <div>
                <span className="text-muted-foreground">thread:</span>{" "}
                <span className="font-medium">{entry.thread}</span>
              </div>
            )}
            {entry.pathname && (
              <div className="col-span-2 md:col-span-3">
                <span className="text-muted-foreground">path:</span>{" "}
                <span className="font-medium">{entry.pathname}</span>
              </div>
            )}
          </div>
          {entry.metadata && Object.keys(entry.metadata).length > 0 && (
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-black/5 p-2 text-[10px] whitespace-pre-wrap">
              {JSON.stringify(entry.metadata, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function LogsConsole({ mode = "application", sourceFilter }: LogsConsoleProps) {
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const filters = useMemo(() => ({
    level: levelFilter === "all" ? undefined : levelFilter,
    source: sourceFilter,
    limit: 200,
  }), [levelFilter, sourceFilter]);

  const { data: logs, isLoading } = useRecentLogs(filters);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
  }, []);

  const toggleExpand = useCallback((id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Select value={levelFilter} onValueChange={setLevelFilter}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Level" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Levels</SelectItem>
            <SelectItem value="error">Error</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="info">Info</SelectItem>
            <SelectItem value="debug">Debug</SelectItem>
          </SelectContent>
        </Select>
        {sourceFilter && (
          <span className="text-muted-foreground text-xs">
            Source filter: <code className="bg-muted rounded px-1">{sourceFilter}</code>
          </span>
        )}
        <span className="text-muted-foreground ml-auto text-xs">
          {logs?.length ?? 0} entries
        </span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="border-border overflow-hidden rounded-lg border"
      >
        {isLoading ? (
          <div className="text-muted-foreground p-4 text-sm">Loading logs…</div>
        ) : !logs || logs.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No logs"
            description="No log entries match your filter."
          />
        ) : (
          logs.map((entry) => (
            <LogEntryRow
              key={entry.id}
              entry={entry}
              isExpanded={expandedIds.has(entry.id)}
              onToggle={() => toggleExpand(entry.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
