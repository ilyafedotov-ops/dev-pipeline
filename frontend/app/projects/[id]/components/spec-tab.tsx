"use client";

import React, { useState } from "react";
import Link from "next/link";

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Clock,
  Download,
  Eye,
  FileSearch,
  FileText,
  Loader2,
  ListPlus,
  MessageSquare,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Sparkles,
  StopCircle,
  Target,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DisabledTooltip } from "@/components/ui/disabled-tooltip";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useAnalyzeSpec,
  useClarifySpec,
  useDetectAmbiguities,
  useGenerateChecklist,
  useGeneratePlan,
  useGenerateSpec,
  useGenerateTasks,
  useInitSpecKit,
  useProject,
  useRunImplement,
  useSpecificationContent,
  useSpecifications,
  useSpecKitStatus,
  useStopSpecRun,
  ClarificationItem,
} from "@/lib/api";
import { getProjectSpecWorkflowPath, getSpecificationReviewPath } from "@/lib/project-routes";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

import { SpecKitWorkflowPanel } from "./speckit-workflow-panel";

/** Extract policy violation findings from a 422 error response */
function extractPolicyFindings(error: unknown): Array<{ code: string; message: string; suggested_fix?: string }> | null {
  if (!error || typeof error !== "object") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const err = error as any;
  // TanStack Query wraps Axios errors
  const response = err?.response ?? err?.error?.response;
  if (!response || typeof response !== "object") return null;
  if (response.status !== 422) return null;
  return response.data?.detail?.findings ?? null;
}

interface SpecTabProps {
  projectId: number;
}

const LAST_UPDATED_BASE = Date.now();

function SpecPreviewContent({ specId }: { specId: number }) {
  const { data, isLoading, error } = useSpecificationContent(specId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-muted-foreground py-8 text-center text-sm">
        Failed to load specification content.
      </div>
    );
  }

  const sections = [
    { label: "Specification", content: data.spec_content },
    { label: "Plan", content: data.plan_content },
    { label: "Tasks", content: data.tasks_content },
    { label: "Checklist", content: data.checklist_content },
    { label: "Analysis", content: data.analysis_content },
  ].filter((s) => s.content);

  if (sections.length === 0) {
    return (
      <div className="text-muted-foreground py-8 text-center text-sm">
        No content available yet. Run specification generation first.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <div key={section.label}>
          <h4 className="mb-2 text-sm font-semibold">{section.label}</h4>
          <pre className="bg-muted max-h-96 overflow-auto whitespace-pre-wrap rounded-lg p-4 text-xs">
            {section.content}
          </pre>
        </div>
      ))}
    </div>
  );
}

/** Inline artifact viewer with tabs for each artifact type */
function SpecArtifactViewer({ specId }: { specId: number }) {
  const { data, isLoading, error } = useSpecificationContent(specId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-muted-foreground py-4 text-center text-sm">
        Failed to load artifact content.
      </div>
    );
  }

  const tabs = [
    { key: "spec", label: "Spec", content: data.spec_content, Icon: FileText },
    { key: "plan", label: "Plan", content: data.plan_content, Icon: Target },
    { key: "tasks", label: "Tasks", content: data.tasks_content, Icon: ListPlus },
    { key: "checklist", label: "Checklist", content: data.checklist_content, Icon: ClipboardCheck },
    { key: "analysis", label: "Analysis", content: data.analysis_content, Icon: FileSearch },
  ].filter((t) => t.content);

  if (tabs.length === 0) {
    return (
      <div className="text-muted-foreground py-4 text-center text-sm">
        No artifacts generated yet. Run Plan / Checklist / Tasks to create artifacts.
      </div>
    );
  }

  return (
    <Tabs defaultValue={tabs[0].key} className="w-full">
      <TabsList className="h-8">
        {tabs.map((tab) => (
          <TabsTrigger key={tab.key} value={tab.key} className="text-xs h-7 px-2.5">
            <tab.Icon className="mr-1.5 h-3 w-3" />
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent key={tab.key} value={tab.key} className="mt-2">
          <pre className="bg-muted max-h-72 overflow-auto whitespace-pre-wrap rounded-lg p-3 text-xs leading-relaxed">
            {tab.content}
          </pre>
        </TabsContent>
      ))}
    </Tabs>
  );
}

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
  const detectAmbiguities = useDetectAmbiguities();

  // Wire up detect-ambiguities response to local state
  React.useEffect(() => {
    if (detectAmbiguities.data?.success && detectAmbiguities.data.clarifications) {
      setDetectedClarifications(detectAmbiguities.data.clarifications);
    }
  }, [detectAmbiguities.data]);
  const generateChecklist = useGenerateChecklist();
  const generatePlan = useGeneratePlan();
  const generateTasks = useGenerateTasks();
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
  const [clarifyMode, setClarifyMode] = useState<"ai" | "manual">("ai");
  const [detectedClarifications, setDetectedClarifications] = useState<ClarificationItem[]>([]);
  const [clarifyAnswers, setClarifyAnswers] = useState<Record<string, string>>({});

  const [activeAction, setActiveAction] = useState<{
    action: string;
    specPath: string;
  } | null>(null);
  const [previewSpecId, setPreviewSpecId] = useState<number | null>(null);
  const [expandedSpecId, setExpandedSpecId] = useState<number | null>(null);

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
    setActiveAction({ action: "checklist", specPath });
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        toast.success(`Checklist generated (${result.item_count} items)`);
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Checklist generation failed");
      }
    } catch (err) {
      const policyFindings = extractPolicyFindings(err);
      if (policyFindings && policyFindings.length > 0) {
        toast.error("Policy violations blocked this operation", {
          description: policyFindings.map(f => `${f.code}: ${f.message}${f.suggested_fix ? ` → ${f.suggested_fix}` : ""}`).join("\n"),
          duration: 8000,
        });
        return;
      }
      toast.error("Checklist generation failed");
    } finally {
      setActiveAction(null);
    }
  };

  const handlePlan = async (specPath: string, specRunId?: number | null) => {
    setActiveAction({ action: "plan", specPath });
    try {
      const result = await generatePlan.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        toast.success("Implementation plan generated");
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Plan generation failed");
      }
    } catch (err) {
      const policyFindings = extractPolicyFindings(err);
      if (policyFindings && policyFindings.length > 0) {
        toast.error("Policy violations blocked this operation", {
          description: policyFindings.map(f => `${f.code}: ${f.message}${f.suggested_fix ? ` → ${f.suggested_fix}` : ""}`).join("\\n"),
          duration: 8000,
        });
        return;
      }
      toast.error("Plan generation failed");
    } finally {
      setActiveAction(null);
    }
  };

  const handleTasks = async (planPath: string | null | undefined, specRunId?: number | null) => {
    if (!planPath) {
      toast.error("Generate a plan first before creating tasks");
      return;
    }
    setActiveAction({ action: "tasks", specPath: planPath });
    try {
      const result = await generateTasks.mutateAsync({
        project_id: projectId,
        plan_path: planPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        toast.success(`Tasks generated (${result.task_count} tasks, ${result.parallelizable_count} parallelizable)`);
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Tasks generation failed");
      }
    } catch (err) {
      const policyFindings = extractPolicyFindings(err);
      if (policyFindings && policyFindings.length > 0) {
        toast.error("Policy violations blocked this operation", {
          description: policyFindings.map(f => `${f.code}: ${f.message}${f.suggested_fix ? ` → ${f.suggested_fix}` : ""}`).join("\\n"),
          duration: 8000,
        });
        return;
      }
      toast.error("Tasks generation failed");
    } finally {
      setActiveAction(null);
    }
  };

  const handleAnalyze = async (
    specPath: string,
    planPath?: string | null,
    tasksPath?: string | null,
    specRunId?: number | null
  ) => {
    setActiveAction({ action: "analyze", specPath });
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
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Analysis failed");
      }
    } catch (err) {
      const policyFindings = extractPolicyFindings(err);
      if (policyFindings && policyFindings.length > 0) {
        toast.error("Policy violations blocked this operation", {
          description: policyFindings.map(f => `${f.code}: ${f.message}${f.suggested_fix ? ` → ${f.suggested_fix}` : ""}`).join("\n"),
          duration: 8000,
        });
        return;
      }
      toast.error("Analysis failed");
    } finally {
      setActiveAction(null);
    }
  };

  const handleImplement = async (specPath: string, specRunId?: number | null) => {
    setActiveAction({ action: "implement", specPath });
    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      });
      if (result.success) {
        const outcome = getImplementSuccessOutcome(result);
        toast.success(outcome.message);
        refetchSpecs();
        refetchStatus();
      } else {
        toast.error(result.error || "Implement initialization failed");
      }
    } catch (err) {
      const policyFindings = extractPolicyFindings(err);
      if (policyFindings && policyFindings.length > 0) {
        toast.error("Policy violations blocked this operation", {
          description: policyFindings.map(f => `${f.code}: ${f.message}${f.suggested_fix ? ` → ${f.suggested_fix}` : ""}`).join("\n"),
          duration: 8000,
        });
        return;
      }
      toast.error("Implement initialization failed");
    } finally {
      setActiveAction(null);
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
                {status.constitution_hash ? `${status.constitution_hash.slice(0, 12)}...` : "N/A"}
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
              const isExpanded = expandedSpecId === spec.id;
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
                  className={`space-y-2 rounded-lg border p-4 transition-colors ${isFailed ? "border-red-500/50 bg-red-500/5" : isExpanded ? "border-primary/30 bg-muted/30" : ""}`}
                >
                  {/* Header row — clickable to expand */}
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => spec.id && setExpandedSpecId(isExpanded ? null : spec.id)}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
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
                  {/* Workflow action buttons — canonical order */}
                  <div className="flex flex-wrap gap-2 pt-2">
                    {spec.id && specPath && !isFailed && !isCleaned && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); setPreviewSpecId(spec.id!); }}
                      >
                        <Eye className="mr-2 h-3.5 w-3.5" />
                        Preview
                      </Button>
                    )}
                    {isFailed && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleRetry(spec.feature_name || spec.title, spec.title); }}
                        disabled={generateSpec.isPending}
                      >
                        {generateSpec.isPending ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="mr-2 h-3.5 w-3.5" />
                        )}
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
                        onClick={(e) => { e.stopPropagation(); if (!specPath) return; setClarifySpecPath(specPath); setClarifySpecRunId(spec.spec_run_id ?? null); setClarifyOpen(true); }}
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
                              ? "Spec file not generated yet."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handlePlan(specPath, spec.spec_run_id); }}
                        disabled={!specPath || isCleaned || isFailed || activeAction?.specPath === specPath}
                      >
                        {activeAction?.action === "plan" && activeAction?.specPath === specPath ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Target className="mr-2 h-3.5 w-3.5" />
                        )}
                        {activeAction?.action === "plan" && activeAction?.specPath === specPath ? "Planning..." : "Plan"}
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleChecklist(specPath, spec.spec_run_id); }}
                        disabled={!specPath || isCleaned || isFailed || activeAction?.specPath === specPath}
                      >
                        {activeAction?.action === "checklist" && activeAction?.specPath === specPath ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ClipboardCheck className="mr-2 h-3.5 w-3.5" />
                        )}
                        {activeAction?.action === "checklist" && activeAction?.specPath === specPath ? "Generating..." : "Checklist"}
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !spec.plan_path
                              ? "Generate a plan first."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleTasks(spec.plan_path, spec.spec_run_id); }}
                        disabled={!spec.plan_path || isCleaned || isFailed || activeAction?.specPath === spec.plan_path}
                      >
                        {activeAction?.action === "tasks" && activeAction?.specPath === spec.plan_path ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ListPlus className="mr-2 h-3.5 w-3.5" />
                        )}
                        {activeAction?.action === "tasks" && activeAction?.specPath === spec.plan_path ? "Generating..." : "Tasks"}
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet."
                              : null
                      }
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleAnalyze(specPath, spec.plan_path, spec.tasks_path, spec.spec_run_id); }}
                        disabled={!specPath || isCleaned || isFailed || activeAction?.specPath === specPath}
                      >
                        {activeAction?.action === "analyze" && activeAction?.specPath === specPath ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <FileSearch className="mr-2 h-3.5 w-3.5" />
                        )}
                        {activeAction?.action === "analyze" && activeAction?.specPath === specPath ? "Analyzing..." : "Analyze"}
                      </Button>
                    </DisabledTooltip>
                    <DisabledTooltip
                      reason={
                        isCleaned
                          ? "This spec run has been cleaned up."
                          : isFailed
                            ? "Spec generation failed — retry before running actions."
                            : !specPath
                              ? "Spec file not generated yet."
                              : null
                      }
                    >
                      <Button
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleImplement(specPath, spec.spec_run_id); }}
                        disabled={!specPath || isCleaned || isFailed || activeAction?.specPath === specPath}
                      >
                        {activeAction?.action === "implement" && activeAction?.specPath === specPath ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <PlayCircle className="mr-2 h-3.5 w-3.5" />
                        )}
                        {activeAction?.action === "implement" && activeAction?.specPath === specPath ? "Implementing..." : "Implement"}
                      </Button>
                    </DisabledTooltip>
                    {spec.spec_run_id && spec.status === "in-progress" && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={stopSpecRun.isPending}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <StopCircle className="mr-2 h-3.5 w-3.5" />
                            Stop Run
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Stop Spec Run</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to stop this spec run? The run will be marked as
                              stopped and any in-progress work will be halted. This action cannot be
                              undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>No, keep running</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive hover:bg-destructive/90 text-white"
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
                  {/* Expanded artifact viewer */}
                  {isExpanded && spec.id && (
                    <div className="border-t pt-3">
                      <SpecArtifactViewer specId={spec.id} />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Preview Specification Dialog */}
      <Dialog open={previewSpecId !== null} onOpenChange={(open) => !open && setPreviewSpecId(null)}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Specification Preview</DialogTitle>
            <DialogDescription>
              View the generated specification and related artifacts.
            </DialogDescription>
          </DialogHeader>
          {previewSpecId !== null && <SpecPreviewContent specId={previewSpecId} />}
        </DialogContent>
      </Dialog>

      <Dialog open={clarifyOpen} onOpenChange={(open) => {
        if (!open) {
          setClarifyOpen(false);
          setDetectedClarifications([]);
          setClarifyAnswers({});
          setClarifyQuestion("");
          setClarifyAnswer("");
          setClarifyNotes("");
        }
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Clarify Specification</DialogTitle>
            <DialogDescription>
              Use AI to detect ambiguities or add manual clarifications.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Mode toggle */}
            <div className="flex gap-2">
              <Button
                variant={clarifyMode === "ai" ? "default" : "outline"}
                size="sm"
                onClick={() => setClarifyMode("ai")}
              >
                <Sparkles className="mr-2 h-3.5 w-3.5" />
                AI Detection
              </Button>
              <Button
                variant={clarifyMode === "manual" ? "default" : "outline"}
                size="sm"
                onClick={() => setClarifyMode("manual")}
              >
                <MessageSquare className="mr-2 h-3.5 w-3.5" />
                Manual
              </Button>
            </div>

            {clarifyMode === "ai" ? (
              /* AI-powered clarification flow */
              <div className="space-y-3">
                {detectedClarifications.length === 0 ? (
                  <div className="flex flex-col items-center gap-3 py-6">
                    <p className="text-muted-foreground text-sm">
                      Click &quot;Detect Ambiguities&quot; to analyze the spec with AI.
                    </p>
                    <Button
                      onClick={() => {
                        if (!clarifySpecPath) return;
                        detectAmbiguities.mutate({
                          project_id: projectId,
                          spec_path: clarifySpecPath,
                          spec_run_id: clarifySpecRunId ?? undefined,
                        });
                      }}
                      disabled={detectAmbiguities.isPending}
                    >
                      {detectAmbiguities.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-3.5 w-3.5" />
                          Detect Ambiguities
                        </>
                      )}
                    </Button>
                    {detectAmbiguities.isError && (
                      <p className="text-xs text-red-500">
                        Failed to detect ambiguities. Try manual mode instead.
                      </p>
                    )}
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-muted-foreground">
                      Found {detectedClarifications.length} ambiguity(ies). Provide answers below.
                    </p>
                    {detectedClarifications.map((item) => (
                      <div key={item.key ?? item.id} className="rounded-lg border p-3 space-y-2">
                        <div className="flex items-start gap-2">
                          <span className="text-sm font-medium flex-1">{item.question}</span>
                          {item.blocking && (
                            <span className="text-xs bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 px-1.5 py-0.5 rounded">
                              blocking
                            </span>
                          )}
                        </div>
                        {item.options && item.options.length > 0 ? (
                          <select
                            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                            value={clarifyAnswers[item.key ?? ""] ?? ""}
                            onChange={(e) =>
                              setClarifyAnswers((prev) => ({
                                ...prev,
                                [item.key ?? ""]: e.target.value,
                              }))
                            }
                          >
                            <option value="">— Select answer —</option>
                            {item.options.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : (
                          <Input
                            placeholder="Your answer..."
                            value={clarifyAnswers[item.key ?? ""] ?? ""}
                            onChange={(e) =>
                              setClarifyAnswers((prev) => ({
                                ...prev,
                                [item.key ?? ""]: e.target.value,
                              }))
                            }
                          />
                        )}
                      </div>
                    ))}
                    <div className="space-y-2">
                      <Label htmlFor="ai-clarify-notes">Additional Notes (optional)</Label>
                      <Textarea
                        id="ai-clarify-notes"
                        placeholder="Any additional context..."
                        rows={2}
                        value={clarifyNotes}
                        onChange={(e) => setClarifyNotes(e.target.value)}
                      />
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" onClick={() => setDetectedClarifications([])}>
                        Re-detect
                      </Button>
                      <Button
                        onClick={async () => {
                          // Build Q&A entries from detected + answered
                          const entries = detectedClarifications
                            .filter((item) => {
                              const key = item.key ?? "";
                              return key && clarifyAnswers[key]?.trim();
                            })
                            .map((item) => ({
                              question: item.question,
                              answer: clarifyAnswers[item.key ?? ""] ?? "",
                            }));
                          if (entries.length === 0 && !clarifyNotes.trim()) {
                            toast.error("Answer at least one question or add notes.");
                            return;
                          }
                          try {
                            await clarifySpec.mutateAsync({
                              project_id: projectId,
                              spec_path: clarifySpecPath!,
                              entries,
                              notes: clarifyNotes || undefined,
                              spec_run_id: clarifySpecRunId ?? undefined,
                            });
                            toast.success(`Clarified ${entries.length} item(s)!`);
                            setClarifyOpen(false);
                            setDetectedClarifications([]);
                            setClarifyAnswers({});
                            setClarifyNotes("");
                          } catch {
                            toast.error("Failed to save clarifications.");
                          }
                        }}
                        disabled={clarifySpec.isPending}
                      >
                        {clarifySpec.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          "Submit Answers"
                        )}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              /* Manual mode — original Q&A + notes form */
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
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
