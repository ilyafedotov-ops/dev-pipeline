"use client";

import { useState } from "react";
import Link from "next/link";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, GitBranch, Loader2, PlayCircle, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import {
  useReconciliationStatus,
  useRunReconciliation,
  useWindmillFlows,
  useWindmillJobs,
} from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";

interface WindmillJob {
  id: string;
  script_path?: string;
  status?: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  job_kind?: string;
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  Running: "default",
  Success: "secondary",
  Failed: "destructive",
  Cancelled: "outline",
  Done: "secondary",
};

function StatusBadge({ status }: { status?: string }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  return <Badge variant={statusVariant[status] ?? "outline"}>{label}</Badge>;
}

const columns: ColumnDef<WindmillJob>[] = [
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => (
      <Link
        href={`/windmill/jobs/${row.original.id}`}
        className="font-mono text-sm hover:underline"
      >
        {row.original.id.slice(0, 12)}
      </Link>
    ),
  },
  {
    accessorKey: "script_path",
    header: "Script",
    cell: ({ row }) => (
      <span className="font-mono text-sm truncate max-w-[300px] block">
        {row.original.script_path ?? "-"}
      </span>
    ),
  },
  {
    accessorKey: "job_kind",
    header: "Kind",
    cell: ({ row }) => (
      <span className="capitalize">{row.original.job_kind ?? "-"}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
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
];

export default function WindmillDashboardPage() {
  const [dryRun, setDryRun] = useState(false);

  const { data: flows, isLoading: flowsLoading } = useWindmillFlows();
  const { data: jobs, isLoading: jobsLoading } = useWindmillJobs({ per_page: 10 });
  const { data: reconStatus, isLoading: reconLoading } = useReconciliationStatus();
  const reconcile = useRunReconciliation();

  const flowsList = Array.isArray(flows) ? flows : [];
  const jobsList = Array.isArray(jobs) ? jobs : (jobs as unknown as { data?: WindmillJob[] })?.data ?? [];
  const activeJobs = jobsList.filter(
    (j: WindmillJob) => j.status === "Running" || j.status === "Queued"
  );

  return (
    <div className="container space-y-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Windmill Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of Windmill automation flows, jobs, and reconciliation
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/windmill/flows">
            <Button variant="outline" size="sm">
              <GitBranch className="mr-2 h-4 w-4" />
              Browse Flows
            </Button>
          </Link>
          <Link href="/windmill/jobs">
            <Button variant="outline" size="sm">
              <Activity className="mr-2 h-4 w-4" />
              All Jobs
            </Button>
          </Link>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Flows</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">
                {flowsLoading ? "..." : flowsList.length}
              </span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active Jobs</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <PlayCircle className="h-5 w-5 text-green-500" />
              <span className="text-2xl font-bold">
                {jobsLoading ? "..." : activeJobs.length}
              </span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Reconciliation</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5 text-orange-500" />
              <span className="text-sm">
                {reconLoading
                  ? "Loading..."
                  : reconStatus?.last_run
                    ? `Last: ${formatRelativeTime(reconStatus.last_run)}`
                    : "Never run"}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Jobs */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Recent Jobs</h2>
        {jobsLoading ? (
          <LoadingState message="Loading jobs..." />
        ) : !jobsList || jobsList.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No jobs found"
            description="No Windmill jobs have been executed yet."
          />
        ) : (
          <DataTable
            columns={columns}
            data={jobsList}
            enableSearch
          />
        )}
      </div>

      {/* Quick Action */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Trigger reconciliation for protocol and step runs</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Checkbox
                id="dry-run"
                checked={dryRun}
                onCheckedChange={(v) => setDryRun(v === true)}
              />
              <label htmlFor="dry-run" className="text-sm cursor-pointer">
                Dry run (preview only)
              </label>
            </div>
            <Button
              onClick={() => reconcile.mutate({ dry_run: dryRun })}
              disabled={reconcile.isPending}
            >
              {reconcile.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Trigger Reconciliation
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
