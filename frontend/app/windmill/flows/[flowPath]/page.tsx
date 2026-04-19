"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, GitBranch, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useWindmillFlow, useWindmillFlowRuns } from "@/lib/api";
import type { ColumnDef } from "@tanstack/react-table";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

interface FlowRun {
  id: string;
  status?: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  Running: "default",
  Success: "secondary",
  Failed: "destructive",
  Cancelled: "outline",
  Done: "secondary",
};

const runColumns: ColumnDef<FlowRun>[] = [
  {
    accessorKey: "id",
    header: "Run ID",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.original.id.slice(0, 16)}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const s = row.original.status;
      if (!s) return <span className="text-muted-foreground">-</span>;
      return <Badge variant={statusVariant[s] ?? "outline"}>{s}</Badge>;
    },
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatRelativeTime(row.original.created_at)}
      </span>
    ),
  },
  {
    accessorKey: "started_at",
    header: "Started",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatDateTime(row.original.started_at)}
      </span>
    ),
  },
  {
    accessorKey: "finished_at",
    header: "Finished",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatDateTime(row.original.finished_at)}
      </span>
    ),
  },
];

export default function FlowDetailPage() {
  const params = useParams();
  const flowPathParam = params?.flowPath;
  const flowPath = Array.isArray(flowPathParam) ? flowPathParam[0] : flowPathParam;

  const { data: flow, isLoading: flowLoading, error: flowError } = useWindmillFlow(flowPath ?? "");
  const { data: runs, isLoading: runsLoading } = useWindmillFlowRuns(flowPath ?? "");

  if (flowLoading) return <LoadingState message="Loading flow..." />;
  if (flowError) {
    const message = flowError instanceof Error ? flowError.message : "Flow not found";
    return (
      <div className="container py-8">
        <EmptyState title="Flow not found" description={message} />
      </div>
    );
  }

  const runsList = Array.isArray(runs) ? runs : (runs as unknown as { data?: FlowRun[] })?.data ?? [];

  return (
    <div className="container space-y-8 py-8">
      <div className="mb-6">
        <Link
          href="/windmill/flows"
          className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Flows
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold">
              <GitBranch className="h-6 w-6 text-blue-500" />
              {flow?.name || flowPath}
            </h1>
            <p className="text-muted-foreground mt-1 font-mono text-sm">{flowPath}</p>
          </div>
        </div>
      </div>

      {/* Flow Info Card */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Flow Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Path</span>
              <span className="font-mono">{flow?.path ?? flowPath}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Name</span>
              <span>{flow?.name ?? "-"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Summary</span>
              <span>{flow?.summary ?? "-"}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Schema</CardTitle>
            <CardDescription>Input/output schema for this flow</CardDescription>
          </CardHeader>
          <CardContent>
            {flow?.schema ? (
              <pre className="bg-muted max-h-64 overflow-auto rounded-lg p-3 font-mono text-xs whitespace-pre-wrap">
                {typeof flow.schema === "string" ? flow.schema : JSON.stringify(flow.schema, null, 2)}
              </pre>
            ) : (
              <span className="text-muted-foreground text-sm">No schema available</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Flow Runs */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Flow Runs</h2>
        {runsLoading ? (
          <LoadingState message="Loading runs..." />
        ) : !runsList || runsList.length === 0 ? (
          <EmptyState
            icon={Loader2}
            title="No runs"
            description="No runs have been executed for this flow."
          />
        ) : (
          <DataTable columns={runColumns} data={runsList} enableSearch />
        )}
      </div>
    </div>
  );
}
