"use client";

import { useEffect, useRef, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Filter,
  Loader2,
  Play,
  RefreshCw,
  Terminal,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable } from "@/components/ui/data-table";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useActiveCLIExecutions,
  useCLIExecution,
  useCLIExecutionLogs,
  useCLIExecutionLogStream,
  useCLIExecutions,
} from "@/lib/api";
import type { CLIExecution } from "@/lib/api/types/cli-executions";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/format";

// ─── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: CLIExecution["status"] }) {
  switch (status) {
    case "running":
      return (
        <Badge className="bg-blue-600 hover:bg-blue-700">
          <Play className="mr-1 h-3 w-3" /> Running
        </Badge>
      );
    case "pending":
      return <Badge variant="secondary">Pending</Badge>;
    case "succeeded":
      return (
        <Badge className="bg-green-600 hover:bg-green-700">
          <CheckCircle2 className="mr-1 h-3 w-3" /> Completed
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" /> Failed
        </Badge>
      );
    case "cancelled":
      return <Badge variant="secondary">Cancelled</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ─── Streaming Log Viewer ────────────────────────────────────────────────────

function StreamingLogViewer({ executionId }: { executionId: string }) {
  const { logs, status, isConnected } = useCLIExecutionLogStream(executionId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      const viewport = scrollRef.current.querySelector("[data-radix-scroll-area-viewport]");
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [logs, autoScroll]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900 px-4 py-2 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <Terminal className="h-3 w-3" />
          <span>STREAM: {executionId.slice(0, 8)}…</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div
              className={cn(
                "h-2 w-2 rounded-full",
                isConnected ? "animate-pulse bg-green-500" : "bg-red-500",
              )}
            />
            <span>{status || "disconnected"}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[10px] text-gray-400 hover:text-gray-200"
            onClick={() => setAutoScroll(!autoScroll)}
          >
            {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1 bg-black p-4 font-mono text-xs" ref={scrollRef}>
        <div className="space-y-1">
          {logs.map((log, i) => (
            <div key={i} className="flex gap-3">
              <span className="w-20 shrink-0 select-none text-gray-600">
                {new Date(log.timestamp)
                  .toLocaleTimeString([], {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                  .split(" ")[0]}
              </span>
              <span
                className={cn(
                  "flex-1 break-all whitespace-pre-wrap",
                  log.level === "error"
                    ? "text-red-400"
                    : log.level === "warn"
                      ? "text-amber-400"
                      : log.level === "debug"
                        ? "text-gray-500"
                        : "text-gray-300",
                )}
              >
                {log.source && <span className="mr-2 text-gray-500">[{log.source}]</span>}
                {log.message}
              </span>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="text-gray-600 italic">Waiting for logs…</div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Historical Log Viewer ───────────────────────────────────────────────────

function HistoricalLogViewer({ executionId }: { executionId: string }) {
  const { data: logData } = useCLIExecutionLogs(executionId);

  return (
    <div className="flex h-full flex-col bg-black font-mono text-xs">
      <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900 px-4 py-2 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <Terminal className="h-3 w-3" />
          <span>Completed Logs</span>
        </div>
        <Badge variant="secondary" className="h-5 text-[10px]">
          {logData?.logs?.length ?? 0} entries
        </Badge>
      </div>
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-1">
          {logData?.logs?.map((log, i) => (
            <div key={i} className="flex gap-3">
              <span className="w-20 shrink-0 select-none text-gray-600">
                {new Date(log.timestamp)
                  .toLocaleTimeString([], {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                  .split(" ")[0]}
              </span>
              <span
                className={cn(
                  "flex-1 break-all whitespace-pre-wrap",
                  log.level === "error"
                    ? "text-red-400"
                    : log.level === "warn"
                      ? "text-amber-400"
                      : "text-gray-300",
                )}
              >
                {log.source && <span className="mr-2 text-gray-500">[{log.source}]</span>}
                {log.message}
              </span>
            </div>
          ))}
          {(!logData?.logs || logData.logs.length === 0) && (
            <div className="text-gray-600 italic">No logs available.</div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function ExecutionsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const { data: executionsData, isLoading, refetch } = useCLIExecutions({
    status: statusFilter !== "all" ? statusFilter : undefined,
  });

  const { data: activeData } = useActiveCLIExecutions();
  const { data: selectedExecution } = useCLIExecution(selectedExecutionId ?? undefined);

  const executions = executionsData?.executions ?? [];
  const activeCount = activeData?.active_count ?? 0;

  const handleRowClick = (exec: CLIExecution) => {
    setSelectedExecutionId(exec.execution_id);
    setDetailOpen(true);
  };

  const columns: ColumnDef<CLIExecution>[] = [
    {
      accessorKey: "execution_id",
      header: "ID",
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.execution_id.slice(0, 12)}</span>
      ),
      size: 130,
    },
    {
      accessorKey: "engine_id",
      header: "Agent",
      cell: ({ row }) => (
        <Badge variant="secondary" className="h-5 text-[10px]">
          {row.original.engine_id}
        </Badge>
      ),
      size: 100,
    },
    {
      accessorKey: "command",
      header: "Command",
      cell: ({ row }) => (
        <code className="max-w-[300px] truncate text-xs">
          {row.original.command || "—"}
        </code>
      ),
      size: 300,
    },
    {
      accessorKey: "execution_type",
      header: "Type",
      cell: ({ row }) => (
        <Badge variant="outline" className="text-[10px] capitalize">
          {row.original.execution_type}
        </Badge>
      ),
      size: 110,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
      size: 130,
    },
    {
      accessorKey: "started_at",
      header: "Started",
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs">
          {formatRelativeTime(row.original.started_at)}
        </span>
      ),
      size: 120,
    },
    {
      id: "duration",
      header: "Duration",
      cell: ({ row }) => {
        const exec = row.original;
        if (exec.duration_seconds != null) {
          return <span className="text-muted-foreground text-xs">{exec.duration_seconds.toFixed(1)}s</span>;
        }
        if (exec.started_at && exec.status === "running") {
          const elapsed = (Date.now() - new Date(exec.started_at).getTime()) / 1000;
          return (
            <span className="text-muted-foreground flex items-center gap-1 text-xs">
              <Clock className="h-3 w-3 animate-spin" />
              {elapsed.toFixed(0)}s
            </span>
          );
        }
        return <span className="text-muted-foreground text-xs">—</span>;
      },
      size: 100,
    },
  ];

  return (
    <div className="container space-y-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">CLI Executions</h1>
          <p className="text-muted-foreground">
            Monitor and inspect CLI execution runs across all agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <div className={cn("h-2 w-2 rounded-full", activeCount > 0 ? "animate-pulse bg-green-500" : "bg-gray-400")} />
            <span className="text-muted-foreground">{activeCount} active</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{executionsData?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold text-blue-500">{activeCount}</div>
              {activeCount > 0 && <Play className="h-4 w-4 animate-pulse text-blue-500" />}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Succeeded</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {executions.filter((e) => e.status === "succeeded").length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">
              {executions.filter((e) => e.status === "failed").length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <Filter className="text-muted-foreground h-4 w-4" />
        <Label className="text-sm text-muted-foreground">Status:</Label>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-9 w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="succeeded">Succeeded</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <DataTable
              columns={columns}
              data={executions}
              onRowClick={handleRowClick}
              enableSearch
              searchPlaceholder="Search executions…"
              className="cursor-pointer"
            />
          </CardContent>
        </Card>
      )}

      {/* Execution Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="flex h-[80vh] max-w-[750px] flex-col p-0">
          <DialogHeader className="border-b px-6 py-4">
            <DialogTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Execution Detail
            </DialogTitle>
            <DialogDescription>
              {selectedExecutionId ? (
                <code className="text-xs">{selectedExecutionId}</code>
              ) : (
                "Select an execution"
              )}
            </DialogDescription>
          </DialogHeader>

          {selectedExecution && (
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Metadata */}
              <div className="space-y-3 border-b px-6 py-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground text-xs">Agent</span>
                    <div>
                      <Badge variant="secondary">{selectedExecution.engine_id}</Badge>
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Status</span>
                    <div>
                      <StatusBadge status={selectedExecution.status} />
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Type</span>
                    <div className="capitalize">{selectedExecution.execution_type}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Duration</span>
                    <div>
                      {selectedExecution.duration_seconds != null
                        ? `${selectedExecution.duration_seconds.toFixed(1)}s`
                        : "—"}
                    </div>
                  </div>
                  {selectedExecution.command && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground text-xs">Command</span>
                      <code className="mt-1 block rounded bg-muted p-2 text-xs">
                        {selectedExecution.command}
                      </code>
                    </div>
                  )}
                  {selectedExecution.error && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground text-xs">Error</span>
                      <div className="mt-1 flex items-start gap-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
                        <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
                        {selectedExecution.error}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Logs */}
              <div className="flex-1 overflow-hidden text-gray-300">
                {selectedExecution.status === "running" || selectedExecution.status === "pending" ? (
                  <StreamingLogViewer executionId={selectedExecution.execution_id} />
                ) : (
                  <HistoricalLogViewer executionId={selectedExecution.execution_id} />
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
