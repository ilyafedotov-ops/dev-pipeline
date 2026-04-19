"use client";

import { useState } from "react";
import Link from "next/link";

import {
  AlertCircle,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusPill } from "@/components/ui/status-pill";
import { useDiscoveryLogs,useOnboarding, useRetryDiscovery, useStartOnboarding } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";

interface OnboardingTabProps {
  projectId: number;
}

export function OnboardingTab({ projectId }: OnboardingTabProps) {
  const { data: onboarding, isLoading } = useOnboarding(projectId);
  const startOnboarding = useStartOnboarding();
  const retryDiscovery = useRetryDiscovery();
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());
  const [showDiscoveryLogs, setShowDiscoveryLogs] = useState(false);
  const {
    data: discoveryLogs,
    isLoading: discoveryLogsLoading,
    error: discoveryLogsError,
  } = useDiscoveryLogs(projectId, 200_000, showDiscoveryLogs);

  if (isLoading) return <LoadingState message="Loading onboarding status..." />;
  if (!onboarding)
    {return <EmptyState title="No onboarding data" description="Onboarding data not available." />;}

  const handleStart = async () => {
    try {
      await startOnboarding.mutateAsync(projectId);
      toast.success("Onboarding started");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start onboarding");
    }
  };

  const handleRetryDiscovery = async () => {
    try {
      const result = await retryDiscovery.mutateAsync(projectId);
      if (result.success) {
        if (result.discovery_warning) {
          toast.warning(result.discovery_warning);
        } else {
          toast.success("Discovery completed");
        }
      } else {
        toast.error(result.discovery_error || "Discovery failed");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to retry discovery");
    }
  };

  const discoveryStage = onboarding.stages.find((stage) =>
    stage.name.toLowerCase().includes("discovery")
  );
  const latestDiscoveryEvent = [...onboarding.events]
    .reverse()
    .find((event) => event.event_type.startsWith("discovery_"));
  const discoveryLogAvailable = Boolean(latestDiscoveryEvent?.metadata?.log_path);

  const toggleEvent = (eventId: number) => {
    setExpandedEvents((current) => {
      const next = new Set(current);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Onboarding Progress</CardTitle>
              <CardDescription>Setup stages for this project</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {onboarding.status === "pending" && (
                <Button onClick={handleStart} disabled={startOnboarding.isPending}>
                  <Play className="mr-2 h-4 w-4" />
                  Start Onboarding
                </Button>
              )}
              {discoveryStage?.status === "failed" && (
                <Button
                  variant="outline"
                  onClick={handleRetryDiscovery}
                  disabled={retryDiscovery.isPending}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry Discovery
                </Button>
              )}
              {discoveryLogAvailable && (
                <Button variant="ghost" onClick={() => setShowDiscoveryLogs(true)}>
                  <FileText className="mr-2 h-4 w-4" />
                  View Discovery Log
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {onboarding.stages.map((stage) => (
              <div key={stage.name} className="flex items-center gap-4">
                <div className="border-muted flex h-8 w-8 items-center justify-center rounded-full border-2">
                  {stage.status === "completed" ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : stage.status === "running" ? (
                    <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                  ) : stage.status === "failed" ? (
                    <XCircle className="text-destructive h-5 w-5" />
                  ) : stage.status === "blocked" ? (
                    <AlertCircle className="h-5 w-5 text-amber-500" />
                  ) : stage.status === "skipped" ? (
                    <Circle className="text-muted-foreground h-5 w-5" />
                  ) : (
                    <Circle className="text-muted-foreground h-5 w-5" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="font-medium capitalize">{stage.name.replace(/_/g, " ")}</p>
                  <p className="text-muted-foreground text-sm">
                    {stage.status === "completed"
                      ? stage.completed_at
                        ? `Completed ${formatRelativeTime(stage.completed_at)}`
                        : "Completed"
                      : stage.status === "running"
                        ? "In progress..."
                        : stage.status === "failed"
                          ? "Failed"
                          : stage.status === "blocked"
                            ? "Blocked on clarifications"
                            : stage.status === "skipped"
                              ? "Skipped"
                              : "Pending"}
                  </p>
                </div>
                <StatusPill status={stage.status} size="sm" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {onboarding.blocking_clarifications > 0 && (
        <Card className="border-amber-500/40 bg-amber-500/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-amber-700">
              <AlertCircle className="h-5 w-5" />
              Blocking Clarifications
            </CardTitle>
            <CardDescription>
              Answer these to unblock onboarding and downstream workflows.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="text-muted-foreground text-sm">
              {onboarding.blocking_clarifications} clarification
              {onboarding.blocking_clarifications > 1 ? "s" : ""} pending
            </div>
            <Button size="sm" asChild>
              <Link href="/clarifications">Open Clarifications Inbox</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {onboarding.events.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Events</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {onboarding.events.slice(0, 10).map((event) => {
                const hasMetadata = event.metadata && Object.keys(event.metadata).length > 0;
                const isExpanded = expandedEvents.has(event.id);
                return (
                  <div key={event.id} className="space-y-2">
                    <div className="flex items-start gap-3 text-sm">
                      <span className="text-muted-foreground min-w-24">
                        {formatRelativeTime(event.created_at)}
                      </span>
                      <span className="text-muted-foreground bg-muted rounded px-1.5 py-0.5 font-mono text-xs">
                        {event.event_type.replace(/_/g, " ")}
                      </span>
                      <span className="flex-1 capitalize">{event.message}</span>
                      {hasMetadata && (
                        <button
                          type="button"
                          onClick={() => toggleEvent(event.id)}
                          className="text-muted-foreground hover:text-foreground text-xs"
                        >
                          {isExpanded ? "Hide details" : "Details"}
                        </button>
                      )}
                    </div>
                    {hasMetadata && isExpanded && (
                      <pre className="bg-muted rounded p-3 text-xs break-words whitespace-pre-wrap">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={showDiscoveryLogs} onOpenChange={setShowDiscoveryLogs}>
        <DialogContent size="4xl" className="h-[80vh] overflow-hidden p-0">
          <DialogHeader className="p-6 pb-2">
            <DialogTitle>Discovery Logs</DialogTitle>
            <DialogDescription>
              {discoveryLogs?.truncated
                ? "Showing first chunk (truncated)."
                : "Latest discovery log output."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-auto px-6 pb-6 font-mono text-xs">
            {discoveryLogsLoading ? (
              <div className="text-muted-foreground">Loading logs...</div>
            ) : discoveryLogsError ? (
              <div className="text-muted-foreground">Failed to load discovery logs.</div>
            ) : discoveryLogs?.content ? (
              <pre className="break-words whitespace-pre-wrap">{discoveryLogs.content}</pre>
            ) : (
              <div className="text-muted-foreground">No discovery logs found yet.</div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
