"use client";

import Link from "next/link";
import { useMemo } from "react";

import {
  Activity,
  AlertCircle,
  ArrowRight,
  Circle,
  Columns3,
  Flame,
  FolderGit2,
  PlayCircle,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAllTasks, useProjects, useProtocols, useRuns } from "@/lib/api";
import type { TaskBoardStatus, TaskPriority } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";
import { useWebSocketEvent } from "@/lib/websocket/hooks";

// ---------------------------------------------------------------------------
// Kanban column configuration
// ---------------------------------------------------------------------------

const KANBAN_COLUMNS: { status: TaskBoardStatus; label: string; color: string }[] = [
  { status: "todo", label: "To Do", color: "bg-slate-400" },
  { status: "in_progress", label: "In Progress", color: "bg-blue-500" },
  { status: "review", label: "Review", color: "bg-amber-500" },
  { status: "testing", label: "Testing", color: "bg-purple-500" },
  { status: "done", label: "Done", color: "bg-green-500" },
];

const MAX_VISIBLE_PER_COLUMN = 4;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PRIORITY_CONFIG: Record<TaskPriority, { color: string; icon: typeof Circle }> = {
  critical: { color: "text-red-600", icon: Flame },
  high: { color: "text-orange-500", icon: Flame },
  medium: { color: "text-yellow-500", icon: Circle },
  low: { color: "text-slate-400", icon: Circle },
};

function PriorityDot({ priority }: { priority: TaskPriority }) {
  const cfg = PRIORITY_CONFIG[priority];
  const Icon = cfg.icon;
  return <Icon className={`h-3 w-3 ${cfg.color} shrink-0`} />;
}

// ---------------------------------------------------------------------------
// Dashboard Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { data: projects } = useProjects();
  const { data: protocols } = useProtocols();
  const { data: runs } = useRuns();
  const { data: allTasks } = useAllTasks();

  // Build a lookup map: project_id → project name
  const projectNameMap = useMemo(() => {
    const map = new Map<number, string>();
    projects?.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [projects]);

  // Group tasks by board_status, excluding backlog
  const groupedTasks = useMemo(() => {
    const groups: Record<string, typeof allTasks> = {};
    for (const col of KANBAN_COLUMNS) {
      groups[col.status] = [];
    }
    if (allTasks) {
      for (const task of allTasks) {
        const group = groups[task.board_status];
        if (group) {
          group.push(task);
        }
      }
    }
    return groups;
  }, [allTasks]);

  const totalTasks = allTasks?.length ?? 0;

  // WebSocket real-time updates: invalidate queries when events arrive
  useWebSocketEvent("events", ["protocol_started", "protocol_completed", "run_completed"], (qc) => {
    qc.invalidateQueries({ queryKey: ["protocols"] });
    qc.invalidateQueries({ queryKey: ["runs"] });
    qc.invalidateQueries({ queryKey: ["projects"] });
  });

  // WebSocket invalidation for tasks
  useWebSocketEvent("events", ["task_created", "task_updated", "task_deleted", "task_moved"], (qc) => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
  });

  const activeProtocols = protocols?.filter((p) => p.status === "running") || [];
  const recentRuns = runs?.slice(0, 5) || [];
  const failedRuns = runs?.filter((r) => r.status === "failed").length || 0;

  const stats = [
    {
      label: "Total Projects",
      value: projects?.length || 0,
      icon: FolderGit2,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
      href: "/projects",
    },
    {
      label: "Active Protocols",
      value: activeProtocols.length,
      icon: Activity,
      color: "text-green-500",
      bg: "bg-green-500/10",
      href: "/protocols",
    },
    {
      label: "Total Runs",
      value: runs?.length || 0,
      icon: PlayCircle,
      color: "text-purple-500",
      bg: "bg-purple-500/10",
      href: "/runs",
    },
    {
      label: "Failed Runs",
      value: failedRuns,
      icon: AlertCircle,
      color: "text-red-500",
      bg: "bg-red-500/10",
      href: "/runs?status=failed",
    },
  ];

  return (
    <div className="container space-y-8 py-8">
      <div>
        <h1 className="mb-2 text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Overview of your DevGodzilla workspace</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Link key={stat.label} href={stat.href}>
              <Card className={`hover:border-primary/50 transition-all hover:shadow-md ${stat.bg}`}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-muted-foreground text-sm font-medium">
                    {stat.label}
                  </CardTitle>
                  <div className="rounded-lg bg-background/50 p-2">
                    <Icon className={`h-5 w-5 ${stat.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Active Protocols
            </CardTitle>
            <CardDescription>Protocols currently running</CardDescription>
          </CardHeader>
          <CardContent>
            {activeProtocols.length === 0 ? (
              <p className="text-muted-foreground py-4 text-sm">No active protocols</p>
            ) : (
              <div className="space-y-3">
                {activeProtocols.slice(0, 5).map((protocol) => (
                  <Link key={protocol.id} href={`/protocols/${protocol.id}`}>
                    <div className="hover:bg-accent flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">{protocol.protocol_name}</p>
                        <p className="text-muted-foreground text-xs">
                          Project: {projects?.find((p) => p.id === protocol.project_id)?.name}
                        </p>
                      </div>
                      <Badge variant="secondary">{protocol.status}</Badge>
                    </div>
                  </Link>
                ))}
                {activeProtocols.length > 5 && (
                  <Link href="/protocols">
                    <Button variant="ghost" size="sm" className="w-full">
                      View all active protocols
                    </Button>
                  </Link>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayCircle className="h-5 w-5" />
              Recent Runs
            </CardTitle>
            <CardDescription>Latest execution runs</CardDescription>
          </CardHeader>
          <CardContent>
            {recentRuns.length === 0 ? (
              <p className="text-muted-foreground py-4 text-sm">No recent runs</p>
            ) : (
              <div className="space-y-3">
                {recentRuns.map((run) => (
                  <Link key={run.run_id} href={`/runs/${run.run_id}`}>
                    <div className="hover:bg-accent flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">{run.job_type}</p>
                        <p className="text-muted-foreground text-xs">
                          {formatRelativeTime(run.created_at)}
                        </p>
                      </div>
                      <Badge
                        variant={
                          run.status === "succeeded"
                            ? "default"
                            : run.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {run.status}
                      </Badge>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Cross-Project Kanban Widget ──────────────────────────────────── */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Columns3 className="h-5 w-5" />
              Task Board
              {totalTasks > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {totalTasks}
                </Badge>
              )}
            </CardTitle>
            <CardDescription>Cross-project overview of all tasks</CardDescription>
          </div>
          <Link href="/execution">
            <Button variant="outline" size="sm" className="gap-1.5">
              Open Board
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {/* Horizontal-scrollable kanban columns */}
          <div className="flex gap-4 overflow-x-auto pb-2">
            {KANBAN_COLUMNS.map((col) => {
              const tasks = groupedTasks[col.status] ?? [];
              const visible = tasks.slice(0, MAX_VISIBLE_PER_COLUMN);
              const remaining = tasks.length - visible.length;
              const totalPoints = tasks.reduce((sum, t) => sum + (t.story_points ?? 0), 0);

              return (
                <div
                  key={col.status}
                  className="min-w-[220px] flex-1 rounded-lg border bg-muted/30"
                >
                  {/* Column header */}
                  <div className="flex items-center justify-between border-b px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block h-2.5 w-2.5 rounded-full ${col.color}`} />
                      <span className="text-sm font-medium">{col.label}</span>
                      <span className="text-muted-foreground text-xs">({tasks.length})</span>
                    </div>
                    {totalPoints > 0 && (
                      <Badge variant="outline" className="text-xs">
                        {totalPoints} pts
                      </Badge>
                    )}
                  </div>

                  {/* Task cards */}
                  <div className="space-y-2 p-2">
                    {visible.length === 0 && (
                      <p className="text-muted-foreground px-1 py-3 text-center text-xs">
                        No tasks
                      </p>
                    )}
                    {visible.map((task) => (
                      <Link key={task.id} href={`/execution?task=${task.id}`}>
                        <div className="hover:bg-accent/50 rounded-md border bg-card p-2 transition-colors">
                          {/* Title row */}
                          <p className="truncate text-sm font-medium leading-snug">
                            {task.title}
                          </p>
                          {/* Meta row */}
                          <div className="mt-1.5 flex items-center gap-2">
                            <PriorityDot priority={task.priority} />
                            <span className="text-muted-foreground max-w-[100px] truncate text-xs">
                              {projectNameMap.get(task.project_id) ?? `Project #${task.project_id}`}
                            </span>
                            {task.story_points != null && task.story_points > 0 && (
                              <Badge variant="secondary" className="ml-auto text-[10px] px-1.5 py-0">
                                {task.story_points} pts
                              </Badge>
                            )}
                          </div>
                        </div>
                      </Link>
                    ))}
                    {remaining > 0 && (
                      <Link href={`/execution?status=${col.status}`}>
                        <p className="text-muted-foreground px-1 text-center text-xs hover:underline">
                          +{remaining} more&hellip;
                        </p>
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link href="/projects">
            <Button variant="outline">View Projects</Button>
          </Link>
          <Link href="/runs">
            <Button variant="outline">View All Runs</Button>
          </Link>
          <Link href="/ops">
            <Button variant="outline">Operations Dashboard</Button>
          </Link>
          <Link href="/policy-packs">
            <Button variant="outline">Policy Packs</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
