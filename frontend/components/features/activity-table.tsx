"use client";

import {
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { ColumnDef } from "@tanstack/react-table";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { formatKeyLabel, formatMetadataValue } from "@/lib/utils/event-metadata";

const DEFAULT_TABLE_HEIGHT = "max-h-[calc(100vh-24rem)] overflow-auto";
const SUMMARY_PRIORITY_KEYS = [
  "status",
  "error",
  "duration_ms",
  "duration_s",
  "step_name",
  "agent_id",
  "job_type",
  "run_id",
  "model",
  "exit_code",
] as const;

type Density = "dense" | "comfortable";

export interface ActivitySortOption<TData> {
  value: string;
  label: string;
  compare: (a: TData, b: TData) => number;
  pinLatest?: boolean;
}

interface EmptyStateConfig {
  icon: LucideIcon;
  title: string;
  description: string;
}

interface ActivityTableProps<TData, TValue> {
  data?: TData[];
  columns: ColumnDef<TData, TValue>[];
  getRowId: (row: TData) => string;
  sortOptions: ActivitySortOption<TData>[];
  defaultSortValue: string;
  storageKey: string;
  searchPlaceholder: string;
  searchAccessor?: (row: TData) => string;
  itemLabel?: string;
  filterControls?: ReactNode;
  statusContent?: ReactNode;
  isLoading?: boolean;
  emptyState: EmptyStateConfig;
  isRowExpanded?: (row: TData) => boolean;
  renderExpandedContent?: (row: TData) => ReactNode;
  enableColumnFilters?: boolean;
  emptyMessage?: string;
  tableHeightClassName?: string;
}

function readStoredView(storageKey: string, defaultSortValue: string) {
  if (typeof window === "undefined") {
    return { sortValue: defaultSortValue, density: "dense" as Density };
  }

  try {
    const stored = localStorage.getItem(storageKey);
    if (!stored) {
      return { sortValue: defaultSortValue, density: "dense" as Density };
    }
    const parsed = JSON.parse(stored) as { sortValue?: string; density?: Density };
    return {
      sortValue: typeof parsed.sortValue === "string" ? parsed.sortValue : defaultSortValue,
      density: parsed.density === "comfortable" ? "comfortable" : "dense",
    };
  } catch {
    return { sortValue: defaultSortValue, density: "dense" as Density };
  }
}

export function MetadataSummary({
  metadata,
  maxItems = 3,
  className,
}: {
  metadata?: Record<string, unknown> | null;
  maxItems?: number;
  className?: string;
}) {
  if (!metadata || Object.keys(metadata).length === 0) {
    return <span className={cn("text-muted-foreground text-xs", className)}>-</span>;
  }

  const prioritized = SUMMARY_PRIORITY_KEYS.filter((key) => metadata[key] != null);
  const remaining = Object.keys(metadata)
    .filter((key) => metadata[key] != null && !prioritized.includes(key as (typeof SUMMARY_PRIORITY_KEYS)[number]))
    .sort();
  const orderedKeys = [...prioritized, ...remaining];
  const visibleKeys = orderedKeys.slice(0, maxItems);
  const hiddenCount = orderedKeys.length - visibleKeys.length;

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {visibleKeys.map((key) => {
        const value = metadata[key];
        const label = key === "duration_ms" || key === "duration_s" ? "Duration" : formatKeyLabel(key);
        const text = `${label}: ${formatMetadataValue(key, value)}`;
        return (
          <Badge
            key={key}
            variant={key === "error" ? "destructive" : "outline"}
            className="max-w-[16rem] truncate text-[10px]"
            title={text}
          >
            {text}
          </Badge>
        );
      })}
      {hiddenCount > 0 ? (
        <Badge variant="secondary" className="text-[10px]">
          +{hiddenCount} more
        </Badge>
      ) : null}
    </div>
  );
}

export function ActivityTable<TData, TValue>({
  data,
  columns,
  getRowId,
  sortOptions,
  defaultSortValue,
  storageKey,
  searchPlaceholder,
  searchAccessor,
  itemLabel = "entries",
  filterControls,
  statusContent,
  isLoading = false,
  emptyState,
  isRowExpanded,
  renderExpandedContent,
  enableColumnFilters = false,
  emptyMessage = "No results.",
  tableHeightClassName = DEFAULT_TABLE_HEIGHT,
}: ActivityTableProps<TData, TValue>) {
  const [view, setView] = useState(() => readStoredView(storageKey, defaultSortValue));
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const previousRowIdsRef = useRef<string[]>([]);
  const previousScrollHeightRef = useRef(0);
  const isAtTopRef = useRef(true);
  const [isAtTop, setIsAtTop] = useState(true);
  const [pendingNewCount, setPendingNewCount] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(storageKey, JSON.stringify(view));
  }, [storageKey, view]);

  const sortOption = useMemo(() => {
    return sortOptions.find((option) => option.value === view.sortValue) ?? sortOptions[0];
  }, [sortOptions, view.sortValue]);

  const sortedData = useMemo(() => {
    const items = [...(data ?? [])];
    items.sort(sortOption.compare);
    return items;
  }, [data, sortOption]);

  const rowIds = useMemo(() => sortedData.map((row) => getRowId(row)), [getRowId, sortedData]);
  const pinLatest = sortOption.pinLatest === true;

  useEffect(() => {
    if (!pinLatest) {
      setPendingNewCount(0);
    }
  }, [pinLatest]);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const nextIsAtTop = container.scrollTop < 24;
    isAtTopRef.current = nextIsAtTop;
    setIsAtTop(nextIsAtTop);
    if (nextIsAtTop) {
      setPendingNewCount(0);
    }
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    handleScroll();
    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [handleScroll, rowIds.length]);

  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      previousRowIdsRef.current = rowIds;
      return;
    }

    if (previousRowIdsRef.current.length === 0) {
      previousRowIdsRef.current = rowIds;
      previousScrollHeightRef.current = container.scrollHeight;
      if (pinLatest) {
        container.scrollTop = 0;
      }
      return;
    }

    const previousIds = previousRowIdsRef.current;
    if (pinLatest) {
      const previousIdSet = new Set(previousIds);
      const prependedCount = rowIds.reduce((count, id) => count + (previousIdSet.has(id) ? 0 : 1), 0);
      const firstRowChanged = rowIds[0] !== previousIds[0];

      if (prependedCount > 0 && firstRowChanged) {
        if (isAtTopRef.current) {
          container.scrollTop = 0;
          setPendingNewCount(0);
        } else {
          const delta = container.scrollHeight - previousScrollHeightRef.current;
          if (delta > 0) {
            container.scrollTop += delta;
          }
          setPendingNewCount((value) => value + prependedCount);
        }
      } else if (isAtTopRef.current) {
        container.scrollTop = 0;
      }
    }

    previousRowIdsRef.current = rowIds;
    previousScrollHeightRef.current = container.scrollHeight;
  }, [pinLatest, rowIds]);

  const jumpToLatest = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: 0, behavior: "smooth" });
    isAtTopRef.current = true;
    setIsAtTop(true);
    setPendingNewCount(0);
  };

  const densityClassName =
    view.density === "dense"
      ? "[&_td]:py-1.5 [&_td]:align-top [&_td]:text-xs [&_th]:h-9 [&_th]:py-2"
      : "[&_td]:py-3 [&_td]:align-top [&_td]:text-sm [&_th]:h-11";

  const liveBadge = pinLatest ? (
    <Badge variant={isAtTop ? "default" : "secondary"} className="text-[10px]">
      {isAtTop ? "Following latest" : pendingNewCount > 0 ? `${pendingNewCount} new` : "Reviewing history"}
    </Badge>
  ) : (
    <Badge variant="outline" className="text-[10px]">
      Manual order
    </Badge>
  );

  if (isLoading) {
    return <LoadingState message={`Loading ${itemLabel}...`} />;
  }

  if (sortedData.length === 0) {
    return (
      <EmptyState
        icon={emptyState.icon}
        title={emptyState.title}
        description={emptyState.description}
      />
    );
  }

  return (
    <DataTable
      columns={columns}
      data={sortedData}
      className={cn("overflow-hidden", densityClassName)}
      enableSearch
      searchPlaceholder={searchPlaceholder}
      enableColumnFilters={enableColumnFilters}
      searchAccessor={searchAccessor}
      toolbarLeadingContent={filterControls}
      toolbarTrailingContent={
        <>
          <Badge variant="secondary" className="text-[10px]">
            {sortedData.length} {itemLabel}
          </Badge>
          {statusContent}
          {liveBadge}
          <Select
            value={view.sortValue}
            onValueChange={(value) => setView((current) => ({ ...current, sortValue: value }))}
          >
            <SelectTrigger className="h-8 w-[150px]">
              <SelectValue placeholder="Sort" />
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={view.density}
            onValueChange={(value: Density) => setView((current) => ({ ...current, density: value }))}
          >
            <SelectTrigger className="h-8 w-[128px]">
              <SelectValue placeholder="Density" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dense">Dense rows</SelectItem>
              <SelectItem value="comfortable">Comfortable</SelectItem>
            </SelectContent>
          </Select>
          {pinLatest && (!isAtTop || pendingNewCount > 0) ? (
            <Button type="button" size="sm" variant="outline" onClick={jumpToLatest}>
              Jump to latest
            </Button>
          ) : null}
        </>
      }
      tableContainerClassName={cn(tableHeightClassName, "overscroll-contain")}
      tableContainerRef={scrollContainerRef}
      stickyHeader
      emptyMessage={emptyMessage}
      isRowExpanded={isRowExpanded}
      renderExpandedContent={renderExpandedContent}
      enableExport
      exportFilename={`${storageKey.replace(/[^a-z0-9_-]/gi, "_")}.csv`}
    />
  );
}
