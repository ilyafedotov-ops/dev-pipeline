"use client";

import Link from "next/link";

import { Activity, AlertCircle,FolderGit2, PlayCircle, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useProjects, useProtocols, useRuns } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { useWebSocketEvent } from "@/lib/websocket/hooks";

export default function DashboardPage() {
  const { data: projects } = useProjects();
  const { data: protocols } = useProtocols();
  const { data: runs } = useRuns();

  // WebSocket real-time updates: invalidate queries when events arrive
  useWebSocketEvent("events", ["protocol_started", "protocol_completed", "run_completed"], (qc) => {
    qc.invalidateQueries({ queryKey: ["protocols"] });
    qc.invalidateQueries({ queryKey: ["runs"] });
    qc.invalidateQueries({ queryKey: ["projects"] });
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
