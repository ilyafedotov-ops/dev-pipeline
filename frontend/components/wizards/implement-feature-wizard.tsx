"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  FileSearch,
  FileText,
  Kanban,
  ListTodo,
  Loader2,
  MessageSquare,
  PlayCircle,
  Target,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";

import { ClarificationDialog, ImplementFeatureWizardSkeleton } from "@/components/shared";
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
import { Separator } from "@/components/ui/separator";
import { StepIndicator } from "@/components/ui/step-indicator";
import {
  useAnalyzeSpec,
  useClarifySpec,
  useCreateProtocolFromSpec,
  useGenerateChecklist,
  useGenerateTasks,
  useImportTasksToSprint,
  useProject,
  useProjectSpecs,
  useRunImplement,
  useSpecKitStatus,
  useSprints,
} from "@/lib/api";
import {
  getProjectExecutionPath,
  getProjectSpecWorkflowPath,
  getProjectSpecWorkspacePath,
} from "@/lib/project-routes";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

const WORKFLOW_STEPS = [
  { id: "spec", label: "Spec", description: "Specification ready" },
  { id: "plan", label: "Plan", description: "Implementation plan" },
  { id: "tasks", label: "Tasks", description: "Task breakdown" },
  { id: "execution", label: "Execution", description: "Run implementation" },
];

interface ImplementFeatureWizardProps {
  projectId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ImplementFeatureWizardModal({
  projectId,
  open,
  onOpenChange,
}: ImplementFeatureWizardProps) {
  const router = useRouter();

  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const { data: specKitStatus, isLoading: statusLoading } = useSpecKitStatus(projectId);
  const { data: specs, isLoading: specsLoading } = useProjectSpecs(projectId);
  const { data: sprints, isLoading: sprintsLoading } = useSprints(projectId);

  const generateTasks = useGenerateTasks();
  const importTasks = useImportTasksToSprint(projectId);
  const clarifySpec = useClarifySpec();
  const generateChecklist = useGenerateChecklist();
  const analyzeSpec = useAnalyzeSpec();
  const runImplement = useRunImplement();
  const createProtocolFromSpec = useCreateProtocolFromSpec();

  const [selectedSpec, setSelectedSpec] = useState<string>("");
  const noSprintValue = "__backlog__";
  const [targetSprint, setTargetSprint] = useState<string>(noSprintValue);
  const [generatedTasksPath, setGeneratedTasksPath] = useState<string | null>(null);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);

  const isLoading = projectLoading || statusLoading || specsLoading || sprintsLoading;
  const isInitialized = specKitStatus?.initialized ?? false;

  const availableSpecs =
    specs?.filter(
      (spec) => spec.status !== "cleaned" && spec.has_plan && !!spec.plan_path && !spec.has_tasks
    ) || [];
  const specsWithTasks = specs?.filter((spec) => spec.status !== "cleaned" && spec.has_tasks) || [];
  const activeSprints =
    sprints?.filter((sprint) => sprint.status === "active" || sprint.status === "planning") || [];
  const defaultSpec = availableSpecs[0]?.plan_path || "";
  const effectiveSpec = selectedSpec || defaultSpec;
  const selectedSpecMeta = specs?.find((spec) => spec.plan_path === effectiveSpec) || null;
  const selectedSpecPath = selectedSpecMeta?.spec_path || "";
  const selectedTasksPath = selectedSpecMeta?.tasks_path || generatedTasksPath || null;
  const selectedSpecRunId = selectedSpecMeta?.spec_run_id ?? null;

  const handleGenerate = async () => {
    if (!effectiveSpec) {
      const errorMsg = "Please select a specification to generate tasks for";
      setWizardError(errorMsg);
      toast.error(errorMsg);
      return;
    }

    setWizardError(null);
    try {
      const result = await generateTasks.mutateAsync({
        project_id: projectId,
        plan_path: effectiveSpec,
        spec_run_id: selectedSpecRunId ?? undefined,
      });

      if (result.success) {
        toast.success(
          `Generated ${result.task_count} tasks (${result.parallelizable_count} parallelizable)`
        );
        if (result.tasks_path) {
          setGeneratedTasksPath(result.tasks_path);
        }

        if (targetSprint !== noSprintValue && result.tasks_path) {
          try {
            await importTasks.mutateAsync(Number.parseInt(targetSprint, 10), {
              spec_path: result.tasks_path,
            });
            toast.success("Tasks imported to execution sprint");
            router.push(getProjectExecutionPath(projectId, targetSprint));
            onOpenChange(false);
          } catch {
            toast.error("Tasks generated, but execution import failed");
            router.push(`/projects/${projectId}?tab=spec&tasks=${result.tasks_path}`);
            onOpenChange(false);
          }
          return;
        }
        if (result.tasks_path) {
          router.push(`/projects/${projectId}?tab=spec&tasks=${result.tasks_path}`);
        }
        onOpenChange(false);
      } else {
        toast.error(result.error || "Failed to generate tasks");
      }
    } catch {
      toast.error("Failed to generate tasks");
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
        plan_path: effectiveSpec || undefined,
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

  const handleCreateProtocol = async () => {
    if (!selectedTasksPath) {
      toast.error("Generate tasks before creating a protocol");
      return;
    }
    try {
      const result = await createProtocolFromSpec.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath || undefined,
        tasks_path: selectedTasksPath,
        spec_run_id: selectedSpecRunId ?? undefined,
      });
      if (result.success && result.protocol) {
        toast.success(`Protocol created with ${result.step_count} steps`);
        router.push(`/protocols/${result.protocol.id}`);
      } else {
        toast.error(result.error || "Protocol creation failed");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Protocol creation failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleWizardClose}>
      <DialogContent size="6xl" className="h-[90vh] overflow-hidden p-0">
        <div className="flex h-full flex-col">
          <DialogHeader className="border-b px-6 py-4">
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-purple-500" />
              Generate Task List
            </DialogTitle>
            <DialogDescription>
              Create implementation tasks from a plan for {project?.name || "this project"}.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
            {isLoading ? (
              <ImplementFeatureWizardSkeleton />
            ) : (
              <>
                {!isInitialized && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <AlertDescription>
                      SpecKit is not initialized.{" "}
                      <Link href={getProjectSpecWorkflowPath(projectId)} className="underline">
                        Run the full SpecKit workflow first
                      </Link>
                    </AlertDescription>
                  </Alert>
                )}

                {isInitialized && availableSpecs.length === 0 && specsWithTasks.length === 0 && (
                  <Alert className="border-blue-500/50 bg-blue-500/10">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <AlertDescription>
                      No implementation plans found.{" "}
                      <Link href={getProjectSpecWorkspacePath(projectId)} className="underline">
                        Open the spec workspace first
                      </Link>
                    </AlertDescription>
                  </Alert>
                )}

                <StepIndicator
                  steps={WORKFLOW_STEPS}
                  currentStep="tasks"
                  completedSteps={new Set(["spec", "plan"])}
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

                <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <ListTodo className="h-5 w-5" />
                          Select Implementation Plan
                        </CardTitle>
                        <CardDescription>
                          Choose a specification that already has a plan
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {availableSpecs.length > 0 ? (
                          <Select value={effectiveSpec} onValueChange={setSelectedSpec}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select a specification with plan..." />
                            </SelectTrigger>
                            <SelectContent>
                              {availableSpecs.map((spec) => (
                                <SelectItem key={spec.path} value={spec.plan_path!}>
                                  <div className="flex items-center gap-2">
                                    <FileText className="h-4 w-4 text-blue-500" />
                                    {spec.name}
                                    <Badge variant="secondary" className="ml-2">
                                      Has Plan
                                    </Badge>
                                  </div>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <div className="text-muted-foreground py-6 text-center">
                            <ListTodo className="mx-auto mb-2 h-8 w-8 opacity-50" />
                            <p>No plans available for task generation</p>
                            {specsWithTasks.length > 0 && (
                              <p className="mt-1 text-sm">
                                All {specsWithTasks.length} plans already have tasks generated
                              </p>
                            )}
                          </div>
                        )}

                        {specsWithTasks.length > 0 && (
                          <div className="mt-4 border-t pt-4">
                            <p className="mb-2 text-sm font-medium">Specs with existing tasks:</p>
                            <div className="flex flex-wrap gap-2">
                              {specsWithTasks.map((spec) => (
                                <Badge key={spec.path} variant="outline">
                                  <CheckCircle2 className="mr-1 h-3 w-3 text-green-500" />
                                  {spec.name}
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
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCreateProtocol}
                            disabled={!selectedTasksPath}
                          >
                            <ClipboardList className="mr-2 h-4 w-4" />
                            Create Protocol
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Kanban className="h-5 w-5" />
                          Assign to Execution (Optional)
                        </CardTitle>
                        <CardDescription>
                          Optionally assign generated tasks directly to an execution sprint
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <Select value={targetSprint} onValueChange={setTargetSprint}>
                          <SelectTrigger>
                            <SelectValue placeholder="No execution (create in backlog)" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={noSprintValue}>
                              No execution (create in backlog)
                            </SelectItem>
                            <Separator className="my-1" />
                            {activeSprints.map((sprint) => (
                              <SelectItem key={sprint.id} value={sprint.id.toString()}>
                                <div className="flex items-center gap-2">
                                  <Target className="h-4 w-4 text-purple-500" />
                                  {sprint.name}
                                  <Badge
                                    variant={sprint.status === "active" ? "default" : "secondary"}
                                  >
                                    {sprint.status}
                                  </Badge>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {activeSprints.length === 0 && (
                          <p className="text-muted-foreground mt-2 text-xs">
                            No active or planning executions.{" "}
                            <Link href={getProjectExecutionPath(projectId)} className="underline">
                              Create an execution sprint first
                            </Link>
                          </p>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="border-purple-500/20 bg-purple-500/5">
                      <CardContent className="pt-6">
                        <div className="flex items-start gap-4">
                          <Wand2 className="mt-0.5 h-6 w-6 text-purple-500" />
                          <div className="flex-1">
                            <p className="mb-2 font-medium">AI-Powered Task Generation</p>
                            <p className="text-muted-foreground mb-4 text-sm">
                              SpecKit will analyze the implementation plan and break it down into:
                            </p>
                            <div className="grid gap-2">
                              <div className="flex items-center gap-2 text-sm">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span>Ordered task list with dependencies</span>
                              </div>
                              <div className="flex items-center gap-2 text-sm">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span>Story point estimates</span>
                              </div>
                              <div className="flex items-center gap-2 text-sm">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span>Parallelizable task identification</span>
                              </div>
                              <div className="flex items-center gap-2 text-sm">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span>Acceptance criteria per task</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="flex justify-between border-t px-6 py-4">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleGenerate} disabled={!effectiveSpec || generateTasks.isPending}>
              {generateTasks.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating Tasks...
                </>
              ) : (
                <>
                  <Wand2 className="mr-2 h-4 w-4" />
                  Generate Tasks
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
