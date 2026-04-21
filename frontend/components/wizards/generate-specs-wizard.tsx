"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileCode,
  FileSearch,
  FileText,
  FolderOpen,
  ListTodo,
  Loader2,
  MessageSquare,
  PlayCircle,
  Sparkles,
  Target,
} from "lucide-react";
import { toast } from "sonner";

import { ClarificationDialog, GenerateSpecsWizardSkeleton } from "@/components/shared";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StepIndicator, useStepNavigation } from "@/components/ui/step-indicator";
import { Textarea } from "@/components/ui/textarea";
import {
  useAnalyzeSpec,
  useClarifySpec,
  useGenerateChecklist,
  useInitSpecKit,
  useProject,
  useRunImplement,
  useRunWorkflow,
  useSpecKitStatus,
} from "@/lib/api";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

// Minimum character length for description (matches backend validation)
const MIN_DESCRIPTION_LENGTH = 10;

const WIZARD_STEPS = [
  { id: "feature-info", label: "Feature Info", description: "Describe the feature" },
  { id: "details", label: "Details", description: "Requirements and constraints" },
  { id: "generate", label: "Generate", description: "Review and generate" },
];

interface GenerateSpecsWizardProps {
  projectId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GenerateSpecsWizardModal({
  projectId,
  open,
  onOpenChange,
}: GenerateSpecsWizardProps) {
  const router = useRouter();
  const {
    currentStep,
    completedSteps,
    goToNext,
    goToPrevious,
    isFirst,
    isLast,
    markComplete,
    reset: resetSteps,
  } = useStepNavigation(WIZARD_STEPS, "feature-info");

  const [formData, setFormData] = useState({
    featureName: "",
    featureDescription: "",
    requirements: "",
    constraints: "",
  });
  const [lastSpecPath, setLastSpecPath] = useState<string | null>(null);
  const [lastSpecRunId, setLastSpecRunId] = useState<number | null>(null);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);

  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const {
    data: specKitStatus,
    isLoading: statusLoading,
    refetch: refetchStatus,
  } = useSpecKitStatus(projectId);

  const initSpecKit = useInitSpecKit();
  const runWorkflow = useRunWorkflow();
  const clarifySpec = useClarifySpec();
  const generateChecklist = useGenerateChecklist();
  const analyzeSpec = useAnalyzeSpec();
  const runImplement = useRunImplement();

  const isLoading = projectLoading || statusLoading;
  const isInitialized = specKitStatus?.initialized ?? false;
  const availableSpecs = useMemo(
    () => (specKitStatus?.specs ?? []).filter((spec) => spec.status !== "cleaned"),
    [specKitStatus]
  );

  const activeSpec = useMemo(() => {
    if (lastSpecRunId) {
      const match = availableSpecs.find((spec) => spec.spec_run_id === lastSpecRunId);
      if (match) return match;
    }
    if (lastSpecPath) {
      return (
        availableSpecs.find(
          (spec) => spec.spec_path === lastSpecPath || spec.path === lastSpecPath
        ) || null
      );
    }
    if (!availableSpecs.length) return null;
    const sorted = [...availableSpecs].sort((a, b) => {
      const aNum = Number.parseInt(a.name.split("-")[0] || "0", 10);
      const bNum = Number.parseInt(b.name.split("-")[0] || "0", 10);
      return bNum - aNum;
    });
    return sorted[0];
  }, [availableSpecs, lastSpecPath, lastSpecRunId]);

  const activeSpecPath = activeSpec?.spec_path || null;

  const buildFullDescription = () => {
    let desc = formData.featureDescription;
    if (formData.requirements) {
      desc += `\n\n## Requirements\n${formData.requirements}`;
    }
    if (formData.constraints) {
      desc += `\n\n## Constraints & Considerations\n${formData.constraints}`;
    }
    return desc;
  };

  // Validation state
  const fullDescription = buildFullDescription();
  const descriptionLength = fullDescription.length;
  const isDescriptionValid = descriptionLength >= MIN_DESCRIPTION_LENGTH;
  const descriptionError =
    !isDescriptionValid && formData.featureDescription.length > 0
      ? `Description must be at least ${MIN_DESCRIPTION_LENGTH} characters (currently ${descriptionLength})`
      : null;

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

  const handleNext = () => {
    setWizardError(null);
    if (!isFirst) {
      markComplete(currentStep);
    }
    goToNext();
  };

  const handleBack = () => {
    if (!isFirst) {
      goToPrevious();
      return;
    }
    onOpenChange(false);
  };

  const handleGenerate = async () => {
    if (!isDescriptionValid) {
      setWizardError(`Description must be at least ${MIN_DESCRIPTION_LENGTH} characters`);
      toast.error(`Description must be at least ${MIN_DESCRIPTION_LENGTH} characters`);
      return;
    }

    try {
      const result = await runWorkflow.mutateAsync({
        project_id: projectId,
        description: fullDescription,
        feature_name: formData.featureName || undefined,
      });

      if (result.success) {
        toast.success(
          result.tasks_path
            ? `Workflow completed: ${result.task_count} tasks generated`
            : "Workflow completed"
        );
        if (result.spec_path) {
          setLastSpecPath(result.spec_path);
          setLastSpecRunId(result.spec_run_id ?? null);
          router.push(`/projects/${projectId}?tab=spec&spec=${result.spec_path}`);
        }
        markComplete("generate");
        onOpenChange(false);
      } else {
        setWizardError(result.error || "Failed to generate specification");
        toast.error(result.error || "Failed to generate specification");
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to generate specification";
      setWizardError(errorMsg);
      toast.error(errorMsg);
    }
  };

  const handleClarify = useCallback(
    async (data: { entries: Array<{ question: string; answer: string }>; notes?: string }) => {
      if (!activeSpecPath) {
        toast.error("No spec available to clarify");
        return;
      }

      try {
        const result = await clarifySpec.mutateAsync({
          project_id: projectId,
          spec_path: activeSpecPath,
          entries: data.entries,
          notes: data.notes,
          spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    [activeSpecPath, projectId, clarifySpec, activeSpec?.spec_run_id]
  );

  const handleOpenClarify = () => {
    setWizardError(null);
    setClarifyOpen(true);
  };

  const handleWizardClose = (newOpen: boolean) => {
    if (!newOpen) {
      // Reset wizard state on close
      resetSteps("feature-info");
      setFormData({
        featureName: "",
        featureDescription: "",
        requirements: "",
        constraints: "",
      });
      setWizardError(null);
    }
    onOpenChange(newOpen);
  };

  const handleChecklist = async () => {
    if (!activeSpecPath) {
      toast.error("No spec available for checklist");
      return;
    }
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    if (!activeSpecPath) {
      toast.error("No spec available for analysis");
      return;
    }
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        plan_path: activeSpec?.plan_path || undefined,
        tasks_path: activeSpec?.tasks_path || undefined,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    if (!activeSpecPath) {
      toast.error("No spec available to implement");
      return;
    }
    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
      });
      if (result.success) {
        const outcome = getImplementSuccessOutcome(result);
        toast.success(outcome.message);
        if (outcome.targetPath) {
          router.push(outcome.targetPath);
        }
      } else {
        toast.error(result.error || "Implementation init failed");
      }
    } catch {
      toast.error("Implementation init failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleWizardClose}>
      <DialogContent size="5xl" className="h-[90vh] max-h-[90vh] overflow-hidden p-0">
        <div className="flex h-full min-h-0 flex-col">
          <DialogHeader className="flex-shrink-0 border-b px-6 py-4">
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-500" />
              Generate Specification
            </DialogTitle>
            <DialogDescription>
              Create a feature spec for {project?.name || "this project"}.
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-6">
            {isLoading ? (
              <GenerateSpecsWizardSkeleton />
            ) : (
              <>
                {!isInitialized && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <AlertDescription className="flex items-center justify-between gap-4">
                      <span>
                        SpecKit is not initialized for this project. Initialize it to start
                        generating specifications.
                      </span>
                      <Button size="sm" onClick={handleInitialize} disabled={initSpecKit.isPending}>
                        {initSpecKit.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <FolderOpen className="mr-2 h-4 w-4" />
                        )}
                        Initialize SpecKit
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}

                {isInitialized && specKitStatus && (
                  <Alert className="border-green-500/50 bg-green-500/10">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <AlertDescription className="flex items-center gap-4">
                      <span>SpecKit is ready!</span>
                      <Badge variant="secondary">{specKitStatus.spec_count} existing specs</Badge>
                    </AlertDescription>
                  </Alert>
                )}

                <StepIndicator
                  steps={WIZARD_STEPS}
                  currentStep={currentStep}
                  completedSteps={completedSteps}
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

                <Card>
                  <CardHeader>
                    <CardTitle>
                      {currentStep === "feature-info" && "Feature Information"}
                      {currentStep === "details" && "Requirements & Constraints"}
                      {currentStep === "generate" && "Review & Generate"}
                    </CardTitle>
                    <CardDescription>
                      {currentStep === "feature-info" && "Describe the feature you want to implement"}
                      {currentStep === "details" && "Provide functional requirements and any constraints"}
                      {currentStep === "generate" && "Review your inputs and generate the specification"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {currentStep === "feature-info" && (
                      <div className="space-y-6">
                        <div className="space-y-2">
                          <Label htmlFor="featureName">Feature Name *</Label>
                          <Input
                            id="featureName"
                            placeholder="e.g., User Authentication System"
                            value={formData.featureName}
                            onChange={(e) =>
                              setFormData({ ...formData, featureName: e.target.value })
                            }
                          />
                          <p className="text-muted-foreground text-xs">
                            A short, descriptive name for this feature
                          </p>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="featureDescription">Description *</Label>
                            <span
                              className={`text-xs ${descriptionError ? "text-destructive" : "text-muted-foreground"}`}
                            >
                              {descriptionLength}/{MIN_DESCRIPTION_LENGTH} min characters
                            </span>
                          </div>
                          <Textarea
                            id="featureDescription"
                            placeholder="Describe what this feature should do, who will use it, and what problem it solves..."
                            rows={8}
                            value={formData.featureDescription}
                            onChange={(e) =>
                              setFormData({ ...formData, featureDescription: e.target.value })
                            }
                            className={descriptionError ? "border-destructive" : ""}
                          />
                          {descriptionError && (
                            <p className="text-destructive text-xs">{descriptionError}</p>
                          )}
                          <p className="text-muted-foreground text-xs">
                            Provide a detailed description of the feature. Minimum{" "}
                            {MIN_DESCRIPTION_LENGTH} characters required.
                          </p>
                        </div>
                      </div>
                    )}

                    {currentStep === "details" && (
                      <div className="space-y-6">
                        <div className="space-y-2">
                          <Label htmlFor="requirements">Functional Requirements</Label>
                          <Textarea
                            id="requirements"
                            placeholder="List the key requirements, user stories, or acceptance criteria..."
                            rows={8}
                            value={formData.requirements}
                            onChange={(e) =>
                              setFormData({ ...formData, requirements: e.target.value })
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="constraints">Constraints & Considerations</Label>
                          <Textarea
                            id="constraints"
                            placeholder="Any technical constraints, security requirements, performance targets..."
                            rows={5}
                            value={formData.constraints}
                            onChange={(e) =>
                              setFormData({ ...formData, constraints: e.target.value })
                            }
                          />
                        </div>
                      </div>
                    )}

                    {currentStep === "generate" && (
                      <div className="space-y-6">
                        <div className="grid gap-6 md:grid-cols-2">
                          <Card className="border-2">
                            <CardHeader>
                              <CardTitle className="flex items-center gap-2 text-base">
                                <FileText className="h-4 w-4" />
                                Feature Summary
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                              <div>
                                <p className="text-muted-foreground text-sm font-medium">Name</p>
                                <p className="font-medium">{formData.featureName}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground text-sm font-medium">Project</p>
                                <p className="text-sm">{project?.name}</p>
                              </div>
                            </CardContent>
                          </Card>

                          <Card className="border-2">
                            <CardHeader>
                              <CardTitle className="flex items-center gap-2 text-base">
                                <Sparkles className="h-4 w-4" />
                                What SpecKit Will Generate
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                              <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2 text-sm">
                                  <FileCode className="h-4 w-4 text-blue-500" />
                                  Feature Specification (spec.md)
                                </span>
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2 text-sm">
                                  <ListTodo className="h-4 w-4 text-emerald-500" />
                                  Implementation Plan (plan.md)
                                </span>
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2 text-sm">
                                  <Target className="h-4 w-4 text-amber-500" />
                                  Task Breakdown (tasks.md)
                                </span>
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                              </div>
                              <div className="border-t" />
                              <div className="text-muted-foreground flex items-center gap-2 text-xs">
                                <Sparkles className="h-3 w-3" />
                                <span>Default happy path: spec → plan → tasks</span>
                              </div>
                            </CardContent>
                          </Card>
                        </div>

                        <Card className="bg-muted/50">
                          <CardHeader>
                            <CardTitle className="text-base">Description Preview</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-muted-foreground max-h-48 overflow-y-auto text-sm whitespace-pre-wrap">
                              {buildFullDescription() || "No description provided"}
                            </p>
                          </CardContent>
                        </Card>

                        <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4">
                          <div className="flex items-start gap-3">
                            <Sparkles className="mt-0.5 h-5 w-5 text-blue-500" />
                            <div>
                              <p className="mb-1 font-medium">AI-Powered Generation</p>
                              <p className="text-muted-foreground text-sm">
                                SpecKit will analyze your description and run the default
                                spec-driven workflow to generate the specification, plan, and task
                                breakdown in one pass.
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="h-5 w-5" />
                      SpecKit Actions
                    </CardTitle>
                    <CardDescription>
                      Run clarify/checklist/analyze/implement on the latest spec
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {activeSpecPath ? (
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={handleOpenClarify}>
                          <MessageSquare className="mr-2 h-4 w-4" />
                          Clarify
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleChecklist}>
                          <ClipboardCheck className="mr-2 h-4 w-4" />
                          Checklist
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleAnalyze}>
                          <FileSearch className="mr-2 h-4 w-4" />
                          Analyze
                        </Button>
                        <Button size="sm" onClick={handleImplement}>
                          <PlayCircle className="mr-2 h-4 w-4" />
                          Implement
                        </Button>
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-sm">
                        Generate a specification to unlock actions.
                      </p>
                    )}
                  </CardContent>
                </Card>

                {isInitialized && specKitStatus && specKitStatus.spec_count > 0 && (
                  <Card className="border-dashed">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <ListTodo className="h-4 w-4" />
                        Existing Specifications
                      </CardTitle>
                      <CardDescription>
                        You have {specKitStatus.spec_count} spec(s) in this project
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid gap-2">
                        {specKitStatus.specs?.slice(0, 5).map((spec) => (
                          <div
                            key={spec.path}
                            className="bg-muted/50 flex items-center justify-between rounded-lg p-3"
                          >
                            <div className="flex items-center gap-3">
                              <FileText className="h-4 w-4 text-blue-500" />
                              <span className="font-medium">{spec.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {spec.has_spec && <Badge variant="outline">Spec</Badge>}
                              {spec.has_plan && <Badge variant="secondary">Plan</Badge>}
                              {spec.has_tasks && <Badge>Tasks</Badge>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </div>

          <div className="flex flex-shrink-0 justify-between border-t px-6 py-4">
            <Button variant="outline" onClick={handleBack}>
              {isFirst ? "Cancel" : "Back"}
            </Button>
            {!isLast ? (
              <Button onClick={handleNext} disabled={!formData.featureName || !isDescriptionValid}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
                <Button
                  onClick={handleGenerate}
                  disabled={runWorkflow.isPending || !isInitialized || !isDescriptionValid}
                >
                {runWorkflow.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Running workflow...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Run Spec Workflow
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        <ClarificationDialog
          open={clarifyOpen}
          onOpenChange={setClarifyOpen}
          onSubmit={handleClarify}
          isLoading={clarifySpec.isPending}
          specName={activeSpec?.name}
        />
      </DialogContent>
    </Dialog>
  );
}
