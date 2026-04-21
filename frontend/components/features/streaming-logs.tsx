"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Activity } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { useLogStream } from "@/lib/api/hooks/use-logs";
import type { AppLogEntry } from "@/lib/api/types";
import { cn } from "@/lib/utils";

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

function StreamLogRow({ entry, isExpanded, onToggle }: {
  entry: AppLogEntry;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const level = entry.level?.toLowerCase() ?? "info";
  const colorClass = levelColors[level] ?? levelColors.info;
  const badgeClass = levelBadgeColors[level] ?? levelBadgeColors.info;
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
        <span className="text-muted-foreground min-w-20 shrink-0">
          {formatTimestamp(entry.timestamp)}
        </span>
        <span
          className={cn(
            "inline-flex min-w-14 shrink-0 items-center justify-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase",
            badgeClass,
          )}
        >
          {level === "warning" ? "WARN" : level.toUpperCase()}
        </span>
        <span className="text-muted-foreground min-w-32 shrink-0 truncate">
          {source}
        </span>
        <span className={cn("min-w-0 flex-1 break-words", colorClass)}>
          {entry.message}
        </span>
      </div>

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
            {entry.metadata && Object.keys(entry.metadata).length > 0 && (
              <pre className="col-span-2 mt-2 max-h-40 overflow-auto rounded bg-black/5 p-2 text-[10px] whitespace-pre-wrap md:col-span-3">
                {JSON.stringify(entry.metadata, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export interface StreamingLogsProps {
  runId: string;
}

export function StreamingLogs({ runId }: StreamingLogsProps) {
  const [entries, setEntries] = useState<AppLogEntry[]>([]);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleLog = useCallback((log: AppLogEntry) => {
    setEntries((prev) => {
      // Cap at 500 entries
      const next = [...prev, log];
      return next.length > 500 ? next.slice(-500) : next;
    });
  }, []);

  const { isConnected } = useLogStream({
    onLog: handleLog,
    enabled: !!runId,
  });

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  const toggleExpand = useCallback((id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const levelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of entries) {
      const l = (e.level ?? "info").toLowerCase();
      counts[l] = (counts[l] || 0) + 1;
    }
    return counts;
  }, [entries]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b px-3 py-2">
        <span className={cn(
          "h-2 w-2 rounded-full",
          isConnected ? "bg-green-500" : "bg-muted-foreground"
        )} />
        <span className="text-muted-foreground text-xs">
          {isConnected ? "Connected" : "Disconnected"}
        </span>
        <span className="text-muted-foreground text-xs">|</span>
        <span className="text-muted-foreground text-xs">{entries.length} entries</span>
        {Object.entries(levelCounts).map(([level, count]) => (
          <span key={level} className={cn("text-xs", levelColors[level])}>
            {level}: {count}
          </span>
        ))}
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto rounded-lg">
        {entries.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="Waiting for logs…"
            description={`Streaming logs for run ${runId.slice(0, 12)}`}
          />
        ) : (
          entries.map((entry) => (
            <StreamLogRow
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
