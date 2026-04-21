"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileSearch,
  FileText,
  Layers,
  Lightbulb,
  Loader2,
  MessageSquare,
  Network,
  PlayCircle,
} from "lucide-react";
import { toast } from "sonner";

import { ClarificationDialog, DesignSolutionWizardSkeleton } from "@/components/shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StepIndicator } from "@/components/ui/step-indicator";
import { Textarea } from "@/components/ui/textarea";
import {
  useAnalyzeSpec,
  useClarifySpec,
  useGenerateChecklist,
  useGeneratePlan,
  useProject,
  useProjectSpecs,
  useRunImplement,
  useSpecKitStatus,
} from "@/lib/api";
import { getProjectSpecWorkflowPath } from "@/lib/project-routes";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

const WORKFLOW_STEPS = [
  { id: "spec", label: "Spec", description: "Specification ready" },
  { id: "plan", label: "Plan", description: "Implementation plan" },
  { id: "tasks", label: "Tasks", description: "Task breakdown" },
  { id: "execution", label: "Execution", description: "Run implementation" },
];

interface DesignSolutionWizardProps {
  projectId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DesignSolutionWizardModal({
  projectId,
  open,
  onOpenChange,
}: DesignSolutionWizardProps) {
  const router = useRouter();
  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const { data: specKitStatus, isLoading: statusLoading } = useSpecKitStatus(projectId);
  const { data: specs, isLoading: specsLoading } = useProjectSpecs(projectId);

  const generatePlan = useGeneratePlan();
  const clarifySpec = useClarifySpec();
  const generateChecklist = useGenerateChecklist();
  const analyzeSpec = useAnalyzeSpec();
  const runImplement = useRunImplement();

  const [selectedSpec, setSelectedSpec] = useState<string>("");
  const [additionalContext, setAdditionalContext] = useState("");
  const [generatedPlanPath, setGeneratedPlanPath] = useState<string | null>(null);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);

  const isLoading = projectLoading || statusLoading || specsLoading;
  const isInitialized = specKitStatus?.initialized ?? false;
  const availableSpecs =
    specs?.filter((s) => s.status !== "cleaned" && s.has_spec && !!s.spec_path && !s.has_plan) ||
    [];
  const specsWithPlans = specs?.filter((s) => s.status !== "cleaned" && s.has_plan) || [];
  const selectedSpecMeta = useMemo(
    () => specs?.find((spec) => spec.spec_path === selectedSpec) || null,
    [specs, selectedSpec]
  );
  const selectedSpecPath = selectedSpec || selectedSpecMeta?.spec_path || "";
  const selectedPlanPath = selectedSpecMeta?.plan_path || generatedPlanPath || null;
  const selectedTasksPath = selectedSpecMeta?.tasks_path || null;
  const selectedSpecRunId = selectedSpecMeta?.spec_run_id ?? null;

  const handleGenerate = async () => {
    if (!selectedSpec) {
      const errorMsg = "Please select a specification to generate a plan for";
      setWizardError(errorMsg);
      toast.error(errorMsg);
      return;
    }

    setWizardError(null);
    try {
      const result = await generatePlan.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpec,
        context: additionalContext || undefined,
        spec_run_id: selectedSpecRunId ?? undefined,
      });

      if (result.success) {
        toast.success("Implementation plan generated successfully!");
        if (result.plan_path) {
          setGeneratedPlanPath(result.plan_path);
          router.push(`/projects/${projectId}?tab=spec&plan=${result.plan_path}`);
        }
        onOpenChange(false);
      } else {
        const errorMsg = result.error || "Failed to generate implementation plan";
        setWizardError(errorMsg);
        toast.error(errorMsg);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to generate implementation plan";
      setWizardError(errorMsg);
      toast.error(errorMsg);
    }
  };

  const handleClarify = useCallback(
    async (data: { entries: Array<{ question: string; answer: string }>; notes?: string }) => {
      if (!selectedSpecPath) {
        toast.error("Select a specification to clarify");
        return;
      }

      try {
        const result = await clarifySpec.mutateAsync({
          project_id: projectId,
          spec_path: selectedSpecPath,
          entries: data.entries,
          notes: data.notes,
          spec_run_id: selectedSpecRunId ?? undefined,
        });
        if (result.success) {
          toast.success(`Clarifications added (${result.clarifications_added})`);
          setClarifyOpen(false);
        } else {
          toast.error(result.error || "Clarification failed");
        }
      } catch {
        toast.error("Clarification failed");
      }
    },
    [selectedSpecPath, projectId, clarifySpec, selectedSpecRunId]
  );

  const handleOpenClarify = () => {
    setWizardError(null);
    setClarifyOpen(true);
  };

  const handleWizardClose = (newOpen: boolean) => {
    if (!newOpen) {
      setWizardError(null);
    }
    onOpenChange(newOpen);
  };

  const handleChecklist = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to run checklist");
      return;
    }

    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        spec_run_id: selectedSpecRunId ?? undefined,
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

  const handleAnalyze = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to analyze");
      return;
    }

    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        plan_path: selectedPlanPath || undefined,
        tasks_path: selectedTasksPath || undefined,
        spec_run_id: selectedSpecRunId ?? undefined,
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

  const handleImplement = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to implement");
      return;
    }

    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        spec_run_id: selectedSpecRunId ?? undefined,
      });
      if (result.success) {
        const outcome = getImplementSuccessOutcome(result);
        toast.success(outcome.message);
        if (outcome.targetPath) {
          router.push(outcome.targetPath);
        }
      } else {
        toast.error(result.error || "Implement init failed");
      }
    } catch {
      toast.error("Implement init failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleWizardClose}>
      <DialogContent size="5xl" className="h-[90vh] overflow-hidden p-0">
        <div className="flex h-full flex-col">
          <DialogHeader className="border-b px-6 py-4">
            <DialogTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-amber-500" />
              Generate Implementation Plan
            </DialogTitle>
            <DialogDescription>
              Create a plan from an existing spec for {project?.name || "this project"}.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
            {isLoading ? (
              <DesignSolutionWizardSkeleton />
            ) : (
              <>
                {!isInitialized && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <AlertDescription>
                      SpecKit is not initialized for this project.{" "}
                      <Link href={getProjectSpecWorkflowPath(projectId)} className="underline">
                        Run the full SpecKit workflow first
                      </Link>{" "}
                      before using the manual planning tool.
                    </AlertDescription>
                  </Alert>
                )}

                {isInitialized && availableSpecs.length === 0 && specs?.length === 0 && (
                  <Alert className="border-blue-500/50 bg-blue-500/10">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <AlertDescription>
                      No specifications found.{" "}
                      <Link href={getProjectSpecWorkflowPath(projectId)} className="underline">
                        Run the full SpecKit workflow first
                      </Link>{" "}
                      before creating an implementation plan manually.
                    </AlertDescription>
                  </Alert>
                )}

                <StepIndicator
                  steps={WORKFLOW_STEPS}
                  currentStep="plan"
                  completedSteps={new Set(["spec"])}
                />

                {wizardError && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="flex items-center justify-between gap-4">
                      <span>{wizardError}</span>
                      <Button size="sm" variant="outline" onClick={() => setWizardError(null)}>
                        Dismiss
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}

                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5" />
                        Select Specification
                      </CardTitle>
                      <CardDescription>
                        Choose an existing specification to generate an implementation plan
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {availableSpecs.length > 0 ? (
                        <Select value={selectedSpec} onValueChange={setSelectedSpec}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a specification..." />
                          </SelectTrigger>
                          <SelectContent>
                            {availableSpecs.map((spec) => (
                              <SelectItem key={spec.path} value={spec.spec_path!}>
                                <div className="flex items-center gap-2">
                                  <FileText className="h-4 w-4 text-blue-500" />
                                  {spec.name}
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <div className="text-muted-foreground py-6 text-center">
                          <FileText className="mx-auto mb-2 h-8 w-8 opacity-50" />
                          <p>No specifications available for plan generation</p>
                          {specsWithPlans.length > 0 && (
                            <p className="mt-1 text-sm">
                              All {specsWithPlans.length} specs already have plans generated
                            </p>
                          )}
                        </div>
                      )}

                      {specsWithPlans.length > 0 && (
                        <div className="mt-4 border-t pt-4">
                          <p className="mb-2 text-sm font-medium">Specs with existing plans:</p>
                          <div className="flex flex-wrap gap-2">
                            {specsWithPlans.map((spec) => (
                              <Badge key={spec.path} variant="secondary">
                                <CheckCircle2 className="mr-1 h-3 w-3 text-green-500" />
                                {spec.name}
                                {spec.has_tasks && <span className="ml-1 text-xs">(+tasks)</span>}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <ClipboardList className="h-5 w-5" />
                        What Will Be Generated
                      </CardTitle>
                      <CardDescription>
                        SpecKit will analyze the specification and create implementation artifacts
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid gap-4 md:grid-cols-3">
                        <div className="bg-muted/50 flex items-start gap-3 rounded-lg p-3">
                          <Layers className="mt-0.5 h-5 w-5 text-amber-500" />
                          <div>
                            <p className="font-medium">Implementation Plan</p>
                            <p className="text-muted-foreground text-xs">
                              Step-by-step implementation guide with phases and milestones
                            </p>
                          </div>
                        </div>
                        <div className="bg-muted/50 flex items-start gap-3 rounded-lg p-3">
                          <Database className="mt-0.5 h-5 w-5 text-blue-500" />
                          <div>
                            <p className="font-medium">Data Model</p>
                            <p className="text-muted-foreground text-xs">
                              Database schema and entity relationships
                            </p>
                          </div>
                        </div>
                        <div className="bg-muted/50 flex items-start gap-3 rounded-lg p-3">
                          <Network className="mt-0.5 h-5 w-5 text-green-500" />
                          <div>
                            <p className="font-medium">API Contracts</p>
                            <p className="text-muted-foreground text-xs">
                              API endpoints, request/response schemas
                            </p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Additional Context (Optional)</CardTitle>
                      <CardDescription>
                        Provide additional context or constraints for the implementation plan
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Textarea
                        placeholder="Any specific implementation preferences, technology constraints, or priorities..."
                        rows={4}
                        value={additionalContext}
                        onChange={(e) => setAdditionalContext(e.target.value)}
                      />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <ClipboardCheck className="h-5 w-5" />
                        SpecKit Actions
                      </CardTitle>
                      <CardDescription>
                        Run clarify/checklist/analyze/implement on the selected spec
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleOpenClarify}
                          disabled={!selectedSpecPath}
                        >
                          <MessageSquare className="mr-2 h-4 w-4" />
                          Clarify
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleChecklist}
                          disabled={!selectedSpecPath}
                        >
                          <ClipboardCheck className="mr-2 h-4 w-4" />
                          Checklist
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleAnalyze}
                          disabled={!selectedSpecPath}
                        >
                          <FileSearch className="mr-2 h-4 w-4" />
                          Analyze
                        </Button>
                        <Button size="sm" onClick={handleImplement} disabled={!selectedSpecPath}>
                          <PlayCircle className="mr-2 h-4 w-4" />
                          Implement
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </div>

          <div className="flex justify-between border-t px-6 py-4">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleGenerate} disabled={!selectedSpec || generatePlan.isPending}>
              {generatePlan.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating Plan...
                </>
              ) : (
                <>
                  <Lightbulb className="mr-2 h-4 w-4" />
                  Generate Implementation Plan
                </>
              )}
            </Button>
          </div>
        </div>

        <ClarificationDialog
          open={clarifyOpen}
          onOpenChange={setClarifyOpen}
          onSubmit={handleClarify}
          isLoading={clarifySpec.isPending}
          specName={selectedSpecMeta?.name}
        />
      </DialogContent>
    </Dialog>
  );
}
