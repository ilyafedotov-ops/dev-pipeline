"use client";

import { useState } from "react";
import Link from "next/link";
import { SpecKitWorkflowPanel } from "./speckit-workflow-panel";

import {
  AlertCircle,
  CheckCircle,
  ClipboardCheck,
  Clock,
  Download,
  FileSearch,
  FileText,
  Loader2,
  MessageSquare,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Sparkles,
  StopCircle,
} from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DisabledTooltip } from "@/components/ui/disabled-tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Textarea } from "@/components/ui/textarea";
import {
  useAnalyzeSpec,
  useClarifySpec,
  useGenerateChecklist,
  useGenerateSpec,
  useInitSpecKit,
  useProject,
  useRunImplement,
  useSpecifications,
  useSpecKitStatus,
  useStopSpecRun,
} from "@/lib/api";
import { getProjectSpecWorkflowPath, getSpecificationReviewPath } from "@/lib/project-routes";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

interface SpecTabProps {
  projectId: number;
}

const LAST_UPDATED_BASE = Date.now();

function getReviewState(spec: {
  has_tasks?: boolean;
  checklist_path?: string | null;
  analysis_path?: string | null;
  implement_path?: string | null;
  protocol_id?: number | null;
}) {
  const hasChecklist = Boolean(spec.checklist_path);
  const hasAnalysis = Boolean(spec.analysis_path);
  const hasExecution = Boolean(spec.protocol_id || spec.implement_path);

  return {
    hasChecklist,
    hasAnalysis,
    hasExecution,
    reviewReady: Boolean(spec.has_tasks && hasChecklist && hasAnalysis),
  };
}

export function SpecTab({ projectId }: SpecTabProps) {
  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const {
    data: status,
    isLoading: statusLoading,
    refetch: refetchStatus,
  } = useSpecKitStatus(projectId);
  const {
    data: specs,
    isLoading: specsLoading,
    refetch: refetchSpecs,
  } = useSpecifications({ project_id: projectId });
  const clarifySpec = useClarifySpec();
  const generateChecklist = useGenerateChecklist();
  const analyzeSpec = useAnalyzeSpec();
  const runImplement = useRunImplement();
  const generateSpec = useGenerateSpec();
  const initSpecKit = useInitSpecKit();
  const stopSpecRun = useStopSpecRun();

  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifySpecPath, setClarifySpecPath] = useState<string | null>(null);
  const [clarifySpecRunId, setClarifySpecRunId] = useState<number | null>(null);
  const [clarifyQuestion, setClarifyQuestion] = useState("");
  const [clarifyAnswer, setClarifyAnswer] = useState("");
  const [clarifyNotes, setClarifyNotes] = useState("");

  const isLoading = projectLoading || statusLoading || specsLoading;

  if (isLoading) return <LoadingState message="Loading specification..." />;

  const handleInitialize = async () => {
    try {
      const result = await initSpecKit.mutateAsync({ project_id: projectId });
      if (result.success) {
        toast.success("SpecKit initialized successfully!");
        refetchStatus();
      } else {
        toast.error(result.error || "Failed to initialize SpecKit");
      }
    } catch {
      toast.error("Failed to initialize SpecKit");
    }
  };

  // Handle uninitialized SpecKit
  if (!status?.initialized) {
    return (
      <div className="space-y-6">
        <div className="py-12 text-center">
          <AlertCircle className="text-muted-foreground mx-auto mb-4 h-12 w-12" />
          <h3 className="mb-2 text-lg font-semibold">SpecKit Not Initialized</h3>
          <p className="text-muted-foreground mb-4 text-sm">
            This project hasn&apos;t been initialized with SpecKit yet.
          </p>
          <div className="space-y-3">
            <Button onClick={handleInitialize} disabled={initSpecKit.isPending}>
              {initSpecKit.isPending ? "Initializing..." : "Initialize SpecKit"}
            </Button>
            <p className="text-muted-foreground text-sm">
              CLI fallback:{" "}
              <code className="bg-muted rounded px-2 py-1">devgodzilla spec init</code>
            </p>
          </div>
        </div>
      </div>
    );
  }

  const handleRefresh = () => {
    refetchStatus();
    refetchSpecs();
  };

  const handleClarify = async () => {
    if (!clarifySpecPath) {
      toast.error("Select a spec to clarify");
      return;
    }

    const hasEntry = clarifyQuestion.trim() && clarifyAnswer.trim();
    const hasNotes = clarifyNotes.trim();

    if (!hasEntry && !hasNotes) {
      toast.error("Provide a question/answer or notes");
      return;
    }

    try {
      const result = await clarifySpec.mutateAsync({
        project_id: projectId,
        spec_path: clarifySpecPath,
        entries: hasEntry
          ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }]
          : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
        spec_run_id: clarifySpecRunId ?? undefined,
      });

      if (result.success) {
        toast.success(`Clarifications added (${result.clarifications_added})`);
        setClarifyOpen(false);
        setClarifyQuestion("");
        setClarifyAnswer("");
        setClarifyNotes("");
        setClarifySpecRunId(null);
      } else {
        toast.error(result.error || "Failed to add clarifications");
      }
    } catch {
      toast.error("Failed to add clarifications");
    }
  };

  const handleChecklist = async (specPath: string, specRunId?: number | null) => {
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        toast.success(`Checklist generated (${result.item_count} items)`);
      } else {
        toast.error(result.error || "Checklist generation failed");
      }
    } catch {
      toast.error("Checklist generation failed");
    }
  };

  const handleAnalyze = async (
    specPath: string,
    planPath?: string | null,
    tasksPath?: string | null,
    specRunId?: number | null
  ) => {
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        plan_path: planPath || undefined,
        tasks_path: tasksPath || undefined,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        toast.success("Analysis report generated");
      } else {
        toast.error(result.error || "Analysis failed");
      }
    } catch {
      toast.error("Analysis failed");
    }
  };

  const handleImplement = async (specPath: string, specRunId?: number | null) => {
    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        const outcome = getImplementSuccessOutcome(result);
        toast.success(outcome.message);
        // Do NOT redirect — stay on spec tab so the user can click
        // "Review Implementation" inline. React Query will refetch
        // the specs list and the review link will appear automatically.
      } else {
        toast.error(result.error || "Implement initialization failed");
      }
    } catch {
      toast.error("Implement initialization failed");
    }
  };

  const handleRetry = async (featureName: string, specName?: string | null) => {
    // Use spec name or feature name as description for retry
    const description = specName || featureName || "Retry specification";
    try {
      toast.info("Retrying specification generation...");
      const result = await generateSpec.mutateAsync({
        project_id: projectId,
        description,
        feature_name: featureName,
      });
      if (result.success) {
        toast.success(`Spec regenerated: ${result.feature_name}`);
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Retry failed");
      }
    } catch {
      toast.error("Retry failed");
    }
  };

  const handleExport = () => {
    if (!status || !specs) return;

    const exportData = {
      project_id: projectId,
      project_name: project?.name,
      generated_at: new Date().toISOString(),
      constitution: {
        version: status.constitution_version,
        hash: status.constitution_hash,
      },
      specifications: specs,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `project-${projectId}-specs.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Get status badge for a specification
  const getStatusBadge = (spec: { has_tasks?: boolean; has_plan?: boolean; status?: string }) => {
    if (spec.status === "cleaned") {
      return (
        <Badge variant="default" className="bg-zinc-500/10 text-zinc-600 hover:bg-zinc-500/20">
          <CheckCircle className="mr-1 h-3 w-3" />
          Cleaned
        </Badge>
      );
    }
    if (spec.status === "failed") {
      return (
        <Badge variant="default" className="bg-red-500/10 text-red-500 hover:bg-red-500/20">
          <AlertCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      );
    }
    if (spec.has_tasks || spec.status === "completed") {
      return (
        <Badge variant="default" className="bg-green-500/10 text-green-500 hover:bg-green-500/20">
          <CheckCircle className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      );
    }
    if (spec.has_plan || spec.status === "in-progress") {
      return (
        <Badge
          variant="default"
          className="bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20"
        >
          <Clock className="mr-1 h-3 w-3" />
          In Progress
        </Badge>
      );
    }
    return (
      <Badge variant="default" className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20">
        <FileText className="mr-1 h-3 w-3" />
        Draft
      </Badge>
    );
  };

  // Get last updated date from most recent spec
  const getLastUpdated = () => {
    if (!specs || specs.length === 0) return "No specs yet";
    const dates = specs
      .filter((s) => s.created_at)
      .map((s) => new Date(s.created_at!))
      .sort((a, b) => b.getTime() - a.getTime());
    if (dates.length === 0) return "Unknown";
    const diff = LAST_UPDATED_BASE - dates[0].getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return "Less than an hour ago";
    if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days === 1 ? "" : "s"} ago`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Project Specification</h3>
          <p className="text-muted-foreground text-sm">
            Technical specification and architecture documentation
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" asChild>
            <Link href={getProjectSpecWorkflowPath(projectId)}>
              <Sparkles className="mr-2 h-4 w-4" />
              Run Spec Workflow
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Regenerate
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Specification Overview</CardTitle>
            <CardDescription>Current project specification status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-muted-foreground text-sm font-medium">Constitution Version</p>
              <p className="text-lg font-semibold">{status.constitution_version || "Not set"}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-sm font-medium">Specifications</p>
              <p className="text-lg font-semibold">{status.spec_count} defined</p>
            </div>
            <div>
              <p className="text-muted-foreground text-sm font-medium">Last Updated</p>
              <p className="text-sm">{getLastUpdated()}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">SpecKit Status</CardTitle>
            <CardDescription>Project initialization and configuration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Initialized</span>
              <Badge variant="default" className="bg-green-500/10 text-green-500">
                <CheckCircle className="mr-1 h-3 w-3" />
                Yes
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Constitution Hash</span>
              <span
                className="text-muted-foreground max-w-[150px] truncate font-mono text-sm"
                title={status.constitution_hash || undefined}
              >
                {status.constitution_hash ? `${status.constitution_hash.slice(0, 12)  }...` : "N/A"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Total Specs</span>
              <span className="text-muted-foreground font-mono text-sm">{status.spec_count}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <SpecKitWorkflowPanel projectId={projectId} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Specifications</CardTitle>
          <CardDescription>Feature specifications and implementation status</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!specs || specs.length === 0 ? (
            <div className="text-muted-foreground py-8 text-center">
              <FileText className="mx-auto mb-2 h-8 w-8 opacity-50" />
              <p className="text-sm">No specifications yet.</p>
              <p className="mt-1 text-xs">
                Generate one with:{" "}
                <code className="bg-muted rounded px-2 py-0.5">devgodzilla spec specify</code>
              </p>
            </div>
          ) : (
            specs.map((spec) => {
              const isCleaned = spec.status === "cleaned";
              const isFailed = spec.status === "failed";
              const specPath = spec.spec_path || spec.path || "";
              const reviewState = getReviewState(spec);
              const reviewPath =
                spec.id &&
                (spec.has_tasks ||
                  reviewState.hasChecklist ||
                  reviewState.hasAnalysis ||
                  reviewState.hasExecution)
                  ? getSpecificationReviewPath(spec.id)
                  : null;
              return (
                <div
                  key={spec.id}
                  className={`space-y-2 rounded-lg border p-4 ${isFailed ? "border-red-500/50 bg-red-500/5" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{spec.title}</h4>
                      {reviewState.reviewReady && (
                        <Badge
                          variant="default"
                          className="bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
                        >
                          Review Ready
                        </Badge>
                      )}
                    </div>
                    {getStatusBadge(spec)}
                  </div>
                  <div className="text-muted-foreground space-y-1 text-sm">
                    <p>
                      <span className="font-medium">Path:</span>{" "}
                      <code className="bg-muted rounded px-1.5 py-0.5 text-xs">{spec.path}</code>
                    </p>
                    <div className="flex gap-4">
                      <span>
                        <span className="font-medium">Plan:</span> {spec.has_plan ? "✓" : "—"}
                      </span>
                      <span>
                        <span className="font-medium">Tasks:</span> {spec.has_tasks ? "✓" : "—"}
                      </span>
                      {spec.linked_tasks > 0 && (
                        <span>
                          <span className="font-medium">Linked:</span> {spec.completed_tasks}/
                          {spec.linked_tasks} tasks
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-4">
                      <span>
                        <span className="font-medium">Checklist:</span>{" "}
                        {reviewState.hasChecklist ? "Ready" : "Missing"}
                      </span>
                      <span>
                        <span className="font-medium">Analysis:</span>{" "}
                        {reviewState.hasAnalysis ? "Ready" : "Missing"}
                      </span>
                      <span>
                        <span className="font-medium">Execution:</span>{" "}
                        {reviewState.hasExecution ? "Bootstrapped" : "Not started"}
                      </span>
                    </div>
                    {isFailed && spec.error_message && (
                      <div className="mt-2 rounded border border-red-500/20 bg-red-500/10 p-2 text-xs text-red-600">
                        <span className="font-medium">Error:</span> {spec.error_message}
                      </div>
                    )}
                    {spec.protocol_id && (
                      <div className="mt-1">
                        <Link
                          href={`/protocols/${spec.protocol_id}`}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          View Protocol #{spec.protocol_id}
                        </Link>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2">
                    {isFailed && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRetry(spec.feature_name || spec.title, spec.title)}
                        disabled={generateSpec.isPending}
                      >
                        <RotateCcw className="mr-2 h-3.5 w-3.5" />
                        {generateSpec.isPending ? "Retrying..." : "Retry"}
                      </Button>
                    )}
                    {reviewPath && (
                      <Button variant="secondary" size="sm" asChild>
                        <Link href={reviewPath}>
                          <FileSearch className="mr-2 h-3.5 w-3.5" />
                          Review Implementation
                        </Link>
                      </Button>
                    )}
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (!specPath) return;
                          setClarifySpecPath(specPath);
                          setClarifySpecRunId(spec.spec_run_id ?? null);
                          setClarifyOpen(true);
                        }}
                        disabled={!specPath || isCleaned || isFailed}
                      >
                        <MessageSquare className="mr-2 h-3.5 w-3.5" />
                        Clarify
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleChecklist(specPath, spec.spec_run_id)}
                        disabled={!specPath || isCleaned || isFailed}
                      >
                        <ClipboardCheck className="mr-2 h-3.5 w-3.5" />
                        Checklist
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleAnalyze(specPath, spec.plan_path, spec.tasks_path, spec.spec_run_id)
                        }
                        disabled={!specPath || isCleaned || isFailed}
                      >
                        <FileSearch className="mr-2 h-3.5 w-3.5" />
                        Analyze
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                      }
                    >
                      <Button
                        size="sm"
                        onClick={() => handleImplement(specPath, spec.spec_run_id)}
                        disabled={!specPath || isCleaned || isFailed}
                      >
                        <PlayCircle className="mr-2 h-3.5 w-3.5" />
                        Implement
                      </Button>
                    </DisabledTooltip>
                    {spec.spec_run_id && spec.status === "in-progress" && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={stopSpecRun.isPending}
                          >
                            <StopCircle className="mr-2 h-3.5 w-3.5" />
                            Stop Run
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Stop Spec Run</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to stop this spec run? The run will be
                              marked as stopped and any in-progress work will be halted.
                              This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>No, keep running</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive text-white hover:bg-destructive/90"
                              disabled={stopSpecRun.isPending}
                              onClick={async () => {
                                try {
                                  const result = await stopSpecRun.mutateAsync(spec.spec_run_id!);
                                  if (result.success) {
                                    toast.success("Spec run stopped successfully");
                                  } else {
                                    toast.error(result.error || "Failed to stop spec run");
                                  }
                                } catch {
                                  toast.error("Failed to stop spec run");
                                }
                              }}
                            >
                              {stopSpecRun.isPending ? (
                                <>
                                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                                  Stopping...
                                </>
                              ) : (
                                "Yes, stop run"
                              )}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SpecKit Actions</CardTitle>
          <CardDescription>
            Run clarification, checklist, analysis, and implementation steps
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!status?.specs || status.specs.length === 0 ? (
            <div className="text-muted-foreground py-6 text-center">
              <FileText className="mx-auto mb-2 h-8 w-8 opacity-50" />
              <p className="text-sm">No spec artifacts available yet.</p>
            </div>
          ) : (
            status.specs.map((spec, index) => {
              const isCleaned = spec.status === "cleaned";
              const specPath = spec.spec_path || spec.path || "";
              const uniqueKey = specPath || spec.name || `spec-${index}`;
              return (
                <div key={uniqueKey} className="space-y-3 rounded-lg border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{spec.name}</p>
                      <p className="text-muted-foreground text-xs">{specPath}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <DisabledTooltip
                        reason={
                          isCleaned
                            ? "This spec run has been cleaned up."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                        }
                      >
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            if (!specPath) return;
                            setClarifySpecPath(specPath);
                            setClarifySpecRunId(spec.spec_run_id ?? null);
                            setClarifyOpen(true);
                          }}
                          disabled={!specPath || isCleaned}
                        >
                          <MessageSquare className="mr-2 h-3.5 w-3.5" />
                          Clarify
                        </Button>
                      </DisabledTooltip>
                      <DisabledTooltip
                        reason={
                          isCleaned
                            ? "This spec run has been cleaned up."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                        }
                      >
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleChecklist(specPath, spec.spec_run_id)}
                          disabled={!specPath || isCleaned}
                        >
                          <ClipboardCheck className="mr-2 h-3.5 w-3.5" />
                          Checklist
                        </Button>
                      </DisabledTooltip>
                      <DisabledTooltip
                        reason={
                          isCleaned
                            ? "This spec run has been cleaned up."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                        }
                      >
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            handleAnalyze(specPath, spec.plan_path, spec.tasks_path, spec.spec_run_id)
                          }
                          disabled={!specPath || isCleaned}
                        >
                          <FileSearch className="mr-2 h-3.5 w-3.5" />
                          Analyze
                        </Button>
                      </DisabledTooltip>
                      <DisabledTooltip
                        reason={
                          isCleaned
                            ? "This spec run has been cleaned up."
                            : !specPath
                              ? "Spec file not generated yet — run Specify first."
                              : null
                        }
                      >
                        <Button
                          size="sm"
                          variant="default"
                          onClick={() => handleImplement(specPath, spec.spec_run_id)}
                          disabled={!specPath || isCleaned}
                        >
                          <PlayCircle className="mr-2 h-3.5 w-3.5" />
                          Implement
                        </Button>
                      </DisabledTooltip>
                      {spec.spec_run_id && spec.status === "in-progress" && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="destructive"
                              size="sm"
                              disabled={stopSpecRun.isPending}
                            >
                              <StopCircle className="mr-2 h-3.5 w-3.5" />
                              Stop Run
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Stop Spec Run</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to stop this spec run? The run will be
                                marked as stopped and any in-progress work will be halted.
                                This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>No, keep running</AlertDialogCancel>
                              <AlertDialogAction
                                className="bg-destructive text-white hover:bg-destructive/90"
                                disabled={stopSpecRun.isPending}
                                onClick={async () => {
                                  try {
                                    const result = await stopSpecRun.mutateAsync(spec.spec_run_id!);
                                    if (result.success) {
                                      toast.success("Spec run stopped successfully");
                                    } else {
                                      toast.error(result.error || "Failed to stop spec run");
                                    }
                                  } catch {
                                    toast.error("Failed to stop spec run");
                                  }
                                }}
                              >
                                {stopSpecRun.isPending ? (
                                  <>
                                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                                    Stopping...
                                  </>
                                ) : (
                                  "Yes, stop run"
                                )}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  </div>
                  <div className="text-muted-foreground flex gap-4 text-xs">
                    <span>Plan: {spec.has_plan ? "✓" : "—"}</span>
                    <span>Tasks: {spec.has_tasks ? "✓" : "—"}</span>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Clarify Specification</DialogTitle>
            <DialogDescription>
              Add a clarification entry or free-form notes to the spec.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="clarify-question">Question (optional)</Label>
              <Input
                id="clarify-question"
                placeholder="What needs clarification?"
                value={clarifyQuestion}
                onChange={(event) => setClarifyQuestion(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clarify-answer">Answer (optional)</Label>
              <Input
                id="clarify-answer"
                placeholder="Provide the resolved answer"
                value={clarifyAnswer}
                onChange={(event) => setClarifyAnswer(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clarify-notes">Notes (optional)</Label>
              <Textarea
                id="clarify-notes"
                placeholder="Additional clarification notes"
                rows={4}
                value={clarifyNotes}
                onChange={(event) => setClarifyNotes(event.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setClarifyOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleClarify} disabled={clarifySpec.isPending}>
                {clarifySpec.isPending ? "Saving..." : "Save Clarification"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
