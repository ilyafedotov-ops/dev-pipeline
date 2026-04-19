"use client";

import { useState } from "react";

import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Play,
  Rocket,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  useGeneratePlan,
  useGenerateTasks,
  useRunWorkflow,
} from "@/lib/api";
import type {
  PlanResponse,
  TasksResponse,
  WorkflowResponse,
} from "@/lib/api/hooks/use-speckit";
import { cn } from "@/lib/utils";

interface SpecKitWorkflowPanelProps {
  projectId: number;
  specPath?: string;
  planPath?: string;
}

// ─── Result Card ─────────────────────────────────────────────────────────────

function ResultCard({
  label,
  result,
  error,
}: {
  label: string;
  result: PlanResponse | TasksResponse | WorkflowResponse | null;
  error: string | null;
}) {
  if (!result && !error) return null;

  const isSuccess = result?.success;
  const hasError = error || (result && !result.success);

  return (
    <div
      className={cn(
        "rounded-lg border p-3 text-sm",
        hasError
          ? "border-red-500/30 bg-red-500/5"
          : "border-green-500/30 bg-green-500/5",
      )}
    >
      <div className="flex items-center gap-2 font-medium">
        {hasError ? (
          <AlertCircle className="h-4 w-4 text-red-500" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-green-500" />
        )}
        {label}
      </div>
      {hasError && (
        <p className="text-destructive mt-1 text-xs">{error || (result as { error?: string })?.error}</p>
      )}
      {isSuccess && result && (
        <div className="text-muted-foreground mt-2 space-y-1 text-xs">
          {"plan_path" in result && result.plan_path && (
            <div>
              <span className="font-medium">Plan:</span> {result.plan_path}
            </div>
          )}
          {"data_model_path" in result && result.data_model_path && (
            <div>
              <span className="font-medium">Data Model:</span> {result.data_model_path}
            </div>
          )}
          {"contracts_path" in result && result.contracts_path && (
            <div>
              <span className="font-medium">Contracts:</span> {result.contracts_path}
            </div>
          )}
          {"tasks_path" in result && result.tasks_path && (
            <div>
              <span className="font-medium">Tasks:</span> {result.tasks_path}
            </div>
          )}
          {"task_count" in result && (
            <div>
              <span className="font-medium">Tasks:</span> {result.task_count} total,{" "}
              {result.parallelizable_count} parallelizable
            </div>
          )}
          {"steps" in result && result.steps && (
            <div className="mt-2 space-y-1">
              {result.steps.map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  {step.success ? (
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                  ) : step.skipped ? (
                    <span className="text-muted-foreground">⊘</span>
                  ) : (
                    <AlertCircle className="h-3 w-3 text-red-500" />
                  )}
                  <span className="capitalize">{step.step}</span>
                  {step.path && <span className="text-muted-foreground">→ {step.path}</span>}
                  {step.error && <span className="text-destructive">({step.error})</span>}
                </div>
              ))}
            </div>
          )}
          {"stopped_after" in result && result.stopped_after && (
            <div className="mt-1">
              <Badge variant="outline" className="text-[10px]">
                Stopped after: {result.stopped_after}
              </Badge>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Panel ──────────────────────────────────────────────────────────────

export function SpecKitWorkflowPanel({ projectId, specPath, planPath }: SpecKitWorkflowPanelProps) {
  const [expanded, setExpanded] = useState(false);

  // Plan generation
  const generatePlan = useGeneratePlan();
  const [planSpecPath, setPlanSpecPath] = useState(specPath ?? "");
  const [planContext, setPlanContext] = useState("");
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  // Task generation
  const generateTasks = useGenerateTasks();
  const [tasksPlanPath, setTasksPlanPath] = useState(planPath ?? "");
  const [tasksResult, setTasksResult] = useState<TasksResponse | null>(null);
  const [tasksError, setTasksError] = useState<string | null>(null);

  // Full workflow
  const runWorkflow = useRunWorkflow();
  const [workflowDesc, setWorkflowDesc] = useState("");
  const [workflowFeature, setWorkflowFeature] = useState("");
  const [workflowStopAfter, setWorkflowStopAfter] = useState<string>("full");
  const [workflowResult, setWorkflowResult] = useState<WorkflowResponse | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);

  const handleGeneratePlan = async () => {
    if (!planSpecPath) {
      toast.error("Spec path is required");
      return;
    }
    setPlanResult(null);
    setPlanError(null);
    try {
      const result = await generatePlan.mutateAsync({
        project_id: projectId,
        spec_path: planSpecPath,
        context: planContext || undefined,
      });
      setPlanResult(result);
      if (result.success) {
        toast.success("Plan generated successfully");
        if (result.plan_path) {
          setTasksPlanPath(result.plan_path);
        }
      } else {
        toast.error(result.error || "Plan generation failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate plan";
      setPlanError(msg);
      toast.error(msg);
    }
  };

  const handleGenerateTasks = async () => {
    if (!tasksPlanPath) {
      toast.error("Plan path is required");
      return;
    }
    setTasksResult(null);
    setTasksError(null);
    try {
      const result = await generateTasks.mutateAsync({
        project_id: projectId,
        plan_path: tasksPlanPath,
      });
      setTasksResult(result);
      if (result.success) {
        toast.success(`Tasks generated: ${result.task_count} total`);
      } else {
        toast.error(result.error || "Task generation failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate tasks";
      setTasksError(msg);
      toast.error(msg);
    }
  };

  const handleRunWorkflow = async () => {
    if (!workflowDesc.trim()) {
      toast.error("Description is required");
      return;
    }
    setWorkflowResult(null);
    setWorkflowError(null);
    try {
      const result = await runWorkflow.mutateAsync({
        project_id: projectId,
        description: workflowDesc.trim(),
        feature_name: workflowFeature.trim() || undefined,
        stop_after: workflowStopAfter === "full" ? undefined : (workflowStopAfter as "spec" | "plan"),
      });
      setWorkflowResult(result);
      if (result.success) {
        toast.success("Workflow completed successfully");
      } else {
        toast.error(result.error || "Workflow failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Workflow failed";
      setWorkflowError(msg);
      toast.error(msg);
    }
  };

  return (
    <Card>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <Zap className="h-4 w-4 text-amber-500" />
            <CardTitle className="text-base">Workflow Actions</CardTitle>
          </div>
          <CardDescription>Generate plans, tasks, or run the full SpecKit pipeline</CardDescription>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-6">
          {/* Generate Plan */}
          <div className="space-y-3">
            <h4 className="flex items-center gap-2 text-sm font-semibold">
              <Play className="h-4 w-4 text-blue-500" />
              Generate Plan
            </h4>
            <p className="text-muted-foreground text-xs">
              Generate an implementation plan from a specification file.
            </p>
            <div className="grid grid-cols-[1fr_auto] gap-3">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Spec Path</Label>
                  <Input
                    value={planSpecPath}
                    onChange={(e) => setPlanSpecPath(e.target.value)}
                    placeholder="/path/to/spec.md"
                    className="h-8 font-mono text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Context (optional)</Label>
                  <Input
                    value={planContext}
                    onChange={(e) => setPlanContext(e.target.value)}
                    placeholder="Additional context for plan generation..."
                    className="h-8 text-xs"
                  />
                </div>
              </div>
              <div className="flex items-end">
                <Button
                  size="sm"
                  onClick={handleGeneratePlan}
                  disabled={generatePlan.isPending || !planSpecPath}
                  className="h-8"
                >
                  {generatePlan.isPending ? (
                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-3 w-3" />
                  )}
                  Generate
                </Button>
              </div>
            </div>
            <ResultCard label="Plan Result" result={planResult} error={planError} />
          </div>

          <Separator />

          {/* Generate Tasks */}
          <div className="space-y-3">
            <h4 className="flex items-center gap-2 text-sm font-semibold">
              <Rocket className="h-4 w-4 text-green-500" />
              Generate Tasks
            </h4>
            <p className="text-muted-foreground text-xs">
              Generate implementation tasks from a plan file.
            </p>
            <div className="grid grid-cols-[1fr_auto] gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Plan Path</Label>
                <Input
                  value={tasksPlanPath}
                  onChange={(e) => setTasksPlanPath(e.target.value)}
                  placeholder="/path/to/plan.md"
                  className="h-8 font-mono text-xs"
                />
              </div>
              <div className="flex items-end">
                <Button
                  size="sm"
                  onClick={handleGenerateTasks}
                  disabled={generateTasks.isPending || !tasksPlanPath}
                  className="h-8"
                >
                  {generateTasks.isPending ? (
                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  ) : (
                    <Rocket className="mr-2 h-3 w-3" />
                  )}
                  Generate
                </Button>
              </div>
            </div>
            <ResultCard label="Tasks Result" result={tasksResult} error={tasksError} />
          </div>

          <Separator />

          {/* Full Workflow */}
          <div className="space-y-3">
            <h4 className="flex items-center gap-2 text-sm font-semibold">
              <Zap className="h-4 w-4 text-amber-500" />
              Full Workflow
            </h4>
            <p className="text-muted-foreground text-xs">
              Run the complete SpecKit pipeline: spec → plan → tasks in one step.
            </p>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Feature Description *</Label>
                <Input
                  value={workflowDesc}
                  onChange={(e) => setWorkflowDesc(e.target.value)}
                  placeholder="Describe the feature you want to build..."
                  className="text-xs"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Feature Name (optional)</Label>
                  <Input
                    value={workflowFeature}
                    onChange={(e) => setWorkflowFeature(e.target.value)}
                    placeholder="my-feature"
                    className="h-8 font-mono text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Stop After</Label>
                  <Select value={workflowStopAfter} onValueChange={setWorkflowStopAfter}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="full">Full Pipeline</SelectItem>
                      <SelectItem value="spec">Spec Only</SelectItem>
                      <SelectItem value="plan">Plan Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button
                size="sm"
                onClick={handleRunWorkflow}
                disabled={runWorkflow.isPending || !workflowDesc.trim()}
              >
                {runWorkflow.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="mr-2 h-4 w-4" />
                )}
                Run Workflow
              </Button>
            </div>
            <ResultCard label="Workflow Result" result={workflowResult} error={workflowError} />
          </div>
        </CardContent>
      )}
    </Card>
  );
}
