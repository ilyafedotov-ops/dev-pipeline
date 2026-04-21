"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import {
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  GitBranch,
  PlayCircle,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  useBuildContextWorkItem,
  useImplementWorkItem,
  useMarkPrReady,
  useProjectProtocols,
  useProjectTaskCycle,
  useQaWorkItem,
  useReviewWorkItem,
  useSprints,
  useStartBrownfieldRun,
} from "@/lib/api";

interface TaskCycleTabProps {
  projectId: number;
}

function toneClass(value: string | null | undefined): string {
  const normalized = (value || "").toLowerCase();
  if (["done", "completed", "ready", "approved", "passed", "available"].includes(normalized)) {
    return "bg-green-500/10 text-green-700";
  }
  if (["failed", "blocked", "needs_changes", "missing"].includes(normalized)) {
    return "bg-red-500/10 text-red-700";
  }
  if (["running", "in_progress", "review", "pending"].includes(normalized)) {
    return "bg-yellow-500/10 text-yellow-700";
  }
  return "bg-blue-500/10 text-blue-700";
}

export function TaskCycleTab({ projectId }: TaskCycleTabProps) {
  const { data: protocols = [], isLoading: protocolsLoading } = useProjectProtocols(projectId);
  const { data: workItems = [], isLoading: workItemsLoading } = useProjectTaskCycle(projectId);
  const { data: sprints = [] } = useSprints(projectId);
  const startBrownfieldRun = useStartBrownfieldRun();
  const buildContext = useBuildContextWorkItem();
  const implementWorkItem = useImplementWorkItem();
  const reviewWorkItem = useReviewWorkItem();
  const qaWorkItem = useQaWorkItem();
  const markPrReady = useMarkPrReady();

  const [featureName, setFeatureName] = useState("");
  const [featureRequest, setFeatureRequest] = useState("");
  const [outputMode, setOutputMode] = useState<
    "task_cycle" | "tasks_only" | "tasks_to_sprint" | "protocol" | "protocol_to_sprint"
  >("task_cycle");
  const [selectedSprintId, setSelectedSprintId] = useState<string>("");
  const [sprintName, setSprintName] = useState("");

  const protocolNames = useMemo(
    () =>
      new Map(
        protocols.map((protocol) => [protocol.id, protocol.protocol_name || `Protocol ${protocol.id}`])
      ),
    [protocols]
  );

  if (protocolsLoading || workItemsLoading) {
    return <LoadingState message="Loading task cycle..." />;
  }

  const handleStart = async () => {
    const trimmedRequest = featureRequest.trim();
    if (!trimmedRequest) {
      toast.error("Describe the brownfield change before starting");
      return;
    }
    if (outputMode === "tasks_to_sprint" && !selectedSprintId) {
      toast.error("Select a sprint before importing tasks");
      return;
    }

    try {
      const result = await startBrownfieldRun.mutateAsync({
        projectId,
        data: {
          feature_request: trimmedRequest,
          feature_name: featureName.trim() || undefined,
          output_mode: outputMode,
          sprint_id: outputMode === "tasks_to_sprint" ? Number(selectedSprintId) : undefined,
          sprint_name: outputMode === "protocol_to_sprint" ? sprintName.trim() || undefined : undefined,
        },
      });
      if (result.sprint) {
        toast.success(`Brownfield run created sprint: ${result.sprint.name}`);
      } else if (result.protocol) {
        toast.success(`Brownfield run created: ${result.protocol.protocol_name}`);
      } else {
        toast.success("Brownfield run created");
      }
      setFeatureRequest("");
      setFeatureName("");
      setSprintName("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start brownfield run");
    }
  };

  const withToast = async (
    action: () => Promise<unknown>,
    successMessage: string,
    fallbackMessage: string
  ) => {
    try {
      await action();
      toast.success(successMessage);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : fallbackMessage);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Task Cycle</h3>
          <p className="text-muted-foreground text-sm">
            Run the brownfield discovery to work-item loop and review items through context,
            implementation, review, QA, and PR readiness.
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="secondary">{workItems.length} work items</Badge>
          <Badge variant="outline">{protocols.length} protocols</Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Start Brownfield Run</CardTitle>
          <CardDescription>
            Run a brownfield feature request into task-cycle work items, tasks, a protocol, or a sprint.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            placeholder="Feature name"
            value={featureName}
            onChange={(event) => setFeatureName(event.target.value)}
          />
          <Textarea
            placeholder="Describe the brownfield change, expected behavior, and constraints"
            value={featureRequest}
            onChange={(event) => setFeatureRequest(event.target.value)}
            rows={5}
          />
          <Select value={outputMode} onValueChange={(value) => setOutputMode(value as typeof outputMode)}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select output mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="task_cycle">Task Cycle</SelectItem>
              <SelectItem value="tasks_only">Tasks Only</SelectItem>
              <SelectItem value="tasks_to_sprint">Tasks To Sprint</SelectItem>
              <SelectItem value="protocol">Protocol</SelectItem>
              <SelectItem value="protocol_to_sprint">Protocol To Sprint</SelectItem>
            </SelectContent>
          </Select>
          {outputMode === "tasks_to_sprint" && (
            <Select value={selectedSprintId} onValueChange={setSelectedSprintId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select existing sprint" />
              </SelectTrigger>
              <SelectContent>
                {sprints.map((sprint) => (
                  <SelectItem key={sprint.id} value={String(sprint.id)}>
                    {sprint.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {outputMode === "protocol_to_sprint" && (
            <Input
              placeholder="Sprint name (optional)"
              value={sprintName}
              onChange={(event) => setSprintName(event.target.value)}
            />
          )}
          <div className="flex justify-end">
            <Button onClick={handleStart} disabled={startBrownfieldRun.isPending}>
              <PlayCircle className="mr-2 h-4 w-4" />
              {startBrownfieldRun.isPending ? "Starting..." : "Start Brownfield Run"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Ready for Context</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {workItems.filter((item) => item.context_status !== "ready").length}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Awaiting Review</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {workItems.filter((item) => item.status === "awaiting_review").length}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">PR Ready</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {workItems.filter((item) => item.pr_ready).length}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Work Items</CardTitle>
          <CardDescription>
            Active task-cycle work items for this project, across all linked protocols.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {workItems.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No brownfield work items yet. Start a run above to create the first task-cycle
              protocol.
            </div>
          ) : (
            workItems.map((item) => (
              <div key={item.id} className="space-y-3 rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="font-medium">{item.title}</h4>
                      <Badge className={toneClass(item.status)}>{item.status}</Badge>
                      <Badge className={toneClass(item.context_status)}>
                        Context {item.context_status}
                      </Badge>
                      <Badge className={toneClass(item.review_status)}>
                        Review {item.review_status}
                      </Badge>
                      <Badge className={toneClass(item.qa_status)}>QA {item.qa_status}</Badge>
                    </div>
                    {item.summary && <p className="text-muted-foreground text-sm">{item.summary}</p>}
                    <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
                      <span>Iterations: {item.iteration_count}/{item.max_iterations}</span>
                      <span>Clarifications: {item.blocking_clarifications}</span>
                      <span>Policy findings: {item.blocking_policy_findings}</span>
                      {item.owner_agent && <span>Owner: {item.owner_agent}</span>}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/protocols/${item.protocol_run_id}`}>
                      <Button variant="outline" size="sm">
                        <GitBranch className="mr-2 h-3.5 w-3.5" />
                        {protocolNames.get(item.protocol_run_id) || `Protocol ${item.protocol_run_id}`}
                        <ArrowUpRight className="ml-2 h-3.5 w-3.5" />
                      </Button>
                    </Link>
                    {item.pr_ready && (
                      <Badge variant="secondary" className="bg-green-500/10 text-green-700">
                        <CheckCircle2 className="mr-1 h-3 w-3" />
                        PR Ready
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      withToast(
                        () =>
                          buildContext.mutateAsync({
                            projectId,
                            workItemId: item.id,
                            protocolRunId: item.protocol_run_id,
                          }),
                        "Context pack refreshed",
                        "Failed to build context"
                      )
                    }
                  >
                    <FileSearch className="mr-2 h-3.5 w-3.5" />
                    Build Context
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      withToast(
                        () =>
                          implementWorkItem.mutateAsync({
                            projectId,
                            workItemId: item.id,
                            protocolRunId: item.protocol_run_id,
                          }),
                        "Implementation started",
                        "Failed to start implementation"
                      )
                    }
                  >
                    <Wrench className="mr-2 h-3.5 w-3.5" />
                    Implement
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      withToast(
                        () =>
                          reviewWorkItem.mutateAsync({
                            projectId,
                            workItemId: item.id,
                            protocolRunId: item.protocol_run_id,
                          }),
                        "Review generated",
                        "Failed to run review"
                      )
                    }
                  >
                    Review
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      withToast(
                        () =>
                          qaWorkItem.mutateAsync({
                            projectId,
                            workItemId: item.id,
                            protocolRunId: item.protocol_run_id,
                          }),
                        "QA completed",
                        "Failed to run QA"
                      )
                    }
                  >
                    <ShieldCheck className="mr-2 h-3.5 w-3.5" />
                    QA
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      withToast(
                        () =>
                          markPrReady.mutateAsync({
                            projectId,
                            workItemId: item.id,
                            protocolRunId: item.protocol_run_id,
                          }),
                        "Marked PR ready",
                        "Failed to mark PR ready"
                      )
                    }
                  >
                    Mark PR Ready
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
