"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { GitBranch, RefreshCw } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { useWindmillFlows } from "@/lib/api";

interface WindmillFlow {
  path: string;
  name?: string;
  summary?: string;
}

const columns: ColumnDef<WindmillFlow>[] = [
  {
    accessorKey: "path",
    header: "Path",
    cell: ({ row }) => (
      <Link
        href={`/windmill/flows/${encodeURIComponent(row.original.path)}`}
        className="font-mono text-sm text-blue-500 hover:underline"
      >
        {row.original.path}
      </Link>
    ),
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.name ?? "-"}</span>
    ),
  },
  {
    accessorKey: "summary",
    header: "Summary",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm line-clamp-2">
        {row.original.summary ?? "-"}
      </span>
    ),
  },
];

export default function WindmillFlowsPage() {
  const router = useRouter();
  const [prefix, setPrefix] = useState("");
  const { data: flows, isLoading, refetch } = useWindmillFlows(prefix || undefined);

  const flowsList = Array.isArray(flows) ? flows : (flows as unknown as { data?: WindmillFlow[] })?.data ?? [];

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
          <h1 className="text-2xl font-bold">Flows</h1>
          <p className="text-muted-foreground">Browse and inspect Windmill automation flows</p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <Input
          placeholder="Filter by prefix (e.g. folders/subfolder)"
          value={prefix}
          onChange={(e) => setPrefix(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {isLoading ? (
        <LoadingState message="Loading flows..." />
      ) : !flowsList || flowsList.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No flows found"
          description={prefix ? `No flows matching prefix "${prefix}"` : "No Windmill flows found."}
        />
      ) : (
        <DataTable
          columns={columns}
          data={flowsList}
          enableSearch
          searchPlaceholder="Search flows..."
          onRowClick={(row) => router.push(`/windmill/flows/${encodeURIComponent(row.path)}`)}
        />
      )}
    </div>
  );
}
