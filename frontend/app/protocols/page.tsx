"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { AlertTriangle, CheckCircle, Filter, Pause, Play, Search, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPill } from "@/components/ui/status-pill";
import { useProjects, useProtocols } from "@/lib/api";
import type { Project, ProtocolRun } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";

const ALL_PROJECTS = "all";

export default function ProtocolsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [projectFilter, setProjectFilter] = useState<string>(ALL_PROJECTS);

  const projectIdFilter =
    projectFilter !== ALL_PROJECTS ? Number.parseInt(projectFilter, 10) : undefined;

  const {
    data: protocols,
    isLoading,
    error,
  } = useProtocols(projectIdFilter ? { project_id: projectIdFilter } : undefined);
  const { data: projects } = useProjects();

  const projectNameById = useMemo(() => {
    const map = new Map<number, string>();
    projects?.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [projects]);

  if (isLoading) return <LoadingState message="Loading protocols..." />;
  if (error) return <EmptyState title="Error loading protocols" description={error.message} />;

  // Filter protocols
  const filteredProtocols = protocols?.filter((protocol) => {
    const matchesSearch =
      search === "" ||
      protocol.protocol_name.toLowerCase().includes(search.toLowerCase()) ||
      protocol.id.toString().includes(search);
    const matchesStatus = statusFilter === "all" || protocol.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Count by status
  const statusCounts = protocols?.reduce(
    (acc, p) => {
      acc[p.status] = (acc[p.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="container py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Protocols</h1>
        <p className="text-muted-foreground">View and manage all protocol executions</p>
      </div>

      {/* Status Overview */}
      <div className="mb-6 grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-muted-foreground text-sm font-medium">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{protocols?.length || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-muted-foreground text-sm font-medium">Running</CardTitle>
            <Play className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statusCounts?.running || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-muted-foreground text-sm font-medium">Paused</CardTitle>
            <Pause className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statusCounts?.paused || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-muted-foreground text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statusCounts?.completed || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-muted-foreground text-sm font-medium">Failed</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statusCounts?.failed || 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-4">
        <div className="relative min-w-[240px] flex-1">
          <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
          <Input
            placeholder="Search protocols by name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={projectFilter} onValueChange={setProjectFilter}>
          <SelectTrigger className="w-[220px]">
            <Filter className="mr-2 h-4 w-4" />
            <SelectValue placeholder="Project" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_PROJECTS}>All Projects</SelectItem>
            {projects?.map((p: Project) => (
              <SelectItem key={p.id} value={p.id.toString()}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <Filter className="mr-2 h-4 w-4" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="blocked">Blocked</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Protocol List */}
      {!filteredProtocols || filteredProtocols.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title={
            search || statusFilter !== "all" || projectFilter !== ALL_PROJECTS
              ? "No protocols found"
              : "No protocols yet"
          }
          description={
            search || statusFilter !== "all" || projectFilter !== ALL_PROJECTS
              ? "Try adjusting your filters"
              : "Protocols will appear here when they are created"
          }
          action={
            search || statusFilter !== "all" || projectFilter !== ALL_PROJECTS ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch("");
                  setStatusFilter("all");
                  setProjectFilter(ALL_PROJECTS);
                }}
              >
                Clear Filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredProtocols.map((protocol) => (
            <ProtocolCard
              key={protocol.id}
              protocol={protocol}
              projectName={projectNameById.get(protocol.project_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProtocolCard({
  protocol,
  projectName,
}: {
  protocol: ProtocolRun;
  projectName: string | undefined;
}) {
  return (
    <Card className="hover:border-primary/50 h-full transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <Link href={`/protocols/${protocol.id}`} className="hover:underline">
              <CardTitle className="truncate text-lg">{protocol.protocol_name}</CardTitle>
            </Link>
            <CardDescription className="text-xs">ID: {protocol.id}</CardDescription>
          </div>
          <StatusPill status={protocol.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground text-xs">Project</p>
            <Link
              href={`/projects/${protocol.project_id}`}
              className="text-primary truncate font-medium hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {projectName ?? `Project ${protocol.project_id}`}
            </Link>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Branch</p>
            <p className="truncate font-medium">{protocol.base_branch || "main"}</p>
          </div>
        </div>

        {protocol.description && (
          <p className="text-muted-foreground line-clamp-2 text-xs">{protocol.description}</p>
        )}

        <p className="text-muted-foreground text-xs">
          Updated {formatRelativeTime(protocol.updated_at)}
        </p>
      </CardContent>
    </Card>
  );
}
