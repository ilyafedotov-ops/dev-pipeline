"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, RefreshCw } from "lucide-react";

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
import { useWindmillJobs } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

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
  Queued: "outline",
};

function StatusBadge({ status }: { status?: string }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  return <Badge variant={statusVariant[status] ?? "outline"}>{label}</Badge>;
}

export default function WindmillJobsPage() {
  const router = useRouter();
  const [jobKind, setJobKind] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: jobs, isLoading, refetch } = useWindmillJobs({
    per_page: 50,
    ...(jobKind !== "all" ? { job_kinds: jobKind } : {}),
  });

  let jobsList: WindmillJob[] = Array.isArray(jobs) ? jobs : (jobs as unknown as { data?: WindmillJob[] })?.data ?? [];

  // Client-side status filter (API may not support it directly)
  if (statusFilter !== "all") {
    jobsList = jobsList.filter((j) => j.status === statusFilter);
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
    {
      id: "duration",
      header: "Duration",
      cell: ({ row }) => {
        const { started_at, finished_at } = row.original;
        if (!started_at) return <span className="text-muted-foreground">-</span>;
        const end = finished_at ? new Date(finished_at) : new Date();
        const diffSec = Math.floor((end.getTime() - new Date(started_at).getTime()) / 1000);
        if (diffSec < 60) return <span>{diffSec}s</span>;
        const diffMin = Math.floor(diffSec / 60);
        if (diffMin < 60) return <span>{diffMin}m {diffSec % 60}s</span>;
        return <span>{Math.floor(diffMin / 60)}h {diffMin % 60}m</span>;
      },
    },
  ];

  return (
    <div className="container space-y-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/windmill"
            className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
          >
            ← Back to Windmill
          </Link>
          <h1 className="text-2xl font-bold">Jobs</h1>
          <p className="text-muted-foreground">Browse and inspect Windmill job executions</p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="flex flex-wrap gap-4">
        <Select value={jobKind} onValueChange={setJobKind}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Job Kind" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Kinds</SelectItem>
            <SelectItem value="script">Script</SelectItem>
            <SelectItem value="flow">Flow</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Running">Running</SelectItem>
            <SelectItem value="Success">Success</SelectItem>
            <SelectItem value="Failed">Failed</SelectItem>
            <SelectItem value="Cancelled">Cancelled</SelectItem>
            <SelectItem value="Done">Done</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <LoadingState message="Loading jobs..." />
      ) : !jobsList || jobsList.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No jobs found"
          description="No Windmill jobs match your filter criteria."
        />
      ) : (
        <DataTable
          columns={columns}
          data={jobsList}
          enableSearch
          searchPlaceholder="Search jobs..."
          onRowClick={(row) => router.push(`/windmill/jobs/${row.id}`)}
        />
      )}
    </div>
  );
}
