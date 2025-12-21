"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  Wand2,
  ListTodo,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  Target,
  Kanban,
  MessageSquare,
  ClipboardList,
  ClipboardCheck,
  FileSearch,
  PlayCircle,
} from "lucide-react"
import {
  useProject,
  useSpecKitStatus,
  useGenerateTasks,
  useProjectSpecs,
  useSprints,
  useImportTasksToSprint,
  useClarifySpec,
  useGenerateChecklist,
  useAnalyzeSpec,
  useRunImplement,
  useCreateProtocolFromSpec,
} from "@/lib/api"

interface ImplementFeatureWizardProps {
  projectId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ImplementFeatureWizardModal({ projectId, open, onOpenChange }: ImplementFeatureWizardProps) {
  const router = useRouter()

  const { data: project, isLoading: projectLoading } = useProject(projectId)
  const { data: specKitStatus, isLoading: statusLoading } = useSpecKitStatus(projectId)
  const { data: specs, isLoading: specsLoading } = useProjectSpecs(projectId)
  const { data: sprints, isLoading: sprintsLoading } = useSprints(projectId)

  const generateTasks = useGenerateTasks()
  const importTasks = useImportTasksToSprint(projectId)
  const clarifySpec = useClarifySpec()
  const generateChecklist = useGenerateChecklist()
  const analyzeSpec = useAnalyzeSpec()
  const runImplement = useRunImplement()
  const createProtocolFromSpec = useCreateProtocolFromSpec()

  const [selectedSpec, setSelectedSpec] = useState<string>("")
  const noSprintValue = "__backlog__"
  const [targetSprint, setTargetSprint] = useState<string>(noSprintValue)
  const [generatedTasksPath, setGeneratedTasksPath] = useState<string | null>(null)
  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifyQuestion, setClarifyQuestion] = useState("")
  const [clarifyAnswer, setClarifyAnswer] = useState("")
  const [clarifyNotes, setClarifyNotes] = useState("")

  const isLoading = projectLoading || statusLoading || specsLoading || sprintsLoading
  const isInitialized = specKitStatus?.initialized ?? false

  const availableSpecs =
    specs?.filter((spec) => spec.status !== "cleaned" && spec.has_plan && !!spec.plan_path && !spec.has_tasks) || []
  const specsWithTasks = specs?.filter((spec) => spec.status !== "cleaned" && spec.has_tasks) || []
  const activeSprints = sprints?.filter((sprint) => sprint.status === "active" || sprint.status === "planning") || []
  const defaultSpec = availableSpecs[0]?.plan_path || ""
  const effectiveSpec = selectedSpec || defaultSpec
  const selectedSpecMeta = specs?.find((spec) => spec.plan_path === effectiveSpec) || null
  const selectedSpecPath = selectedSpecMeta?.spec_path || ""
  const selectedTasksPath = selectedSpecMeta?.tasks_path || generatedTasksPath || null
  const selectedSpecRunId = selectedSpecMeta?.spec_run_id ?? null

  const handleGenerate = async () => {
    if (!effectiveSpec) {
      toast.error("Please select a specification to generate tasks for")
      return
    }

    try {
      const result = await generateTasks.mutateAsync({
        project_id: projectId,
        plan_path: effectiveSpec,
        spec_run_id: selectedSpecRunId ?? undefined,
      })

      if (result.success) {
        toast.success(`Generated ${result.task_count} tasks (${result.parallelizable_count} parallelizable)`)
        if (result.tasks_path) {
          setGeneratedTasksPath(result.tasks_path)
        }

        if (targetSprint !== noSprintValue && result.tasks_path) {
          try {
            await importTasks.mutateAsync(Number.parseInt(targetSprint, 10), {
              spec_path: result.tasks_path,
            })
            toast.success("Tasks imported to execution sprint")
            router.push(`/projects/${projectId}/execution?sprint=${targetSprint}`)
            onOpenChange(false)
          } catch {
            toast.error("Tasks generated, but execution import failed")
            router.push(`/projects/${projectId}?tab=spec&tasks=${result.tasks_path}`)
            onOpenChange(false)
          }
          return
        }
        if (result.tasks_path) {
          router.push(`/projects/${projectId}?tab=spec&tasks=${result.tasks_path}`)
        }
        onOpenChange(false)
      } else {
        toast.error(result.error || "Failed to generate tasks")
      }
    } catch {
      toast.error("Failed to generate tasks")
    }
  }

  const handleClarify = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to clarify")
      return
    }

    const hasEntry = clarifyQuestion.trim() && clarifyAnswer.trim()
    const hasNotes = clarifyNotes.trim()

    if (!hasEntry && !hasNotes) {
      toast.error("Provide a question/answer or notes")
      return
    }

    try {
      const result = await clarifySpec.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        entries: hasEntry ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }] : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
        spec_run_id: selectedSpecRunId ?? undefined,
      })
      if (result.success) {
        toast.success(`Clarifications added (${result.clarifications_added})`)
        setClarifyOpen(false)
        setClarifyQuestion("")
        setClarifyAnswer("")
        setClarifyNotes("")
      } else {
        toast.error(result.error || "Clarification failed")
      }
    } catch {
      toast.error("Clarification failed")
    }
  }

  const handleChecklist = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to run checklist")
      return
    }

    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        spec_run_id: selectedSpecRunId ?? undefined,
      })
      if (result.success) {
        toast.success(`Checklist generated (${result.item_count} items)`)
      } else {
        toast.error(result.error || "Checklist generation failed")
      }
    } catch {
      toast.error("Checklist generation failed")
    }
  }

  const handleAnalyze = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to analyze")
      return
    }

    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        plan_path: effectiveSpec || undefined,
        tasks_path: selectedTasksPath || undefined,
        spec_run_id: selectedSpecRunId ?? undefined,
      })
      if (result.success) {
        toast.success("Analysis report generated")
      } else {
        toast.error(result.error || "Analysis failed")
      }
    } catch {
      toast.error("Analysis failed")
    }
  }

  const handleImplement = async () => {
    if (!selectedSpecPath) {
      toast.error("Select a specification to implement")
      return
    }

    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath,
        spec_run_id: selectedSpecRunId ?? undefined,
      })
      if (result.success) {
        toast.success("Implementation run initialized")
      } else {
        toast.error(result.error || "Implement init failed")
      }
    } catch {
      toast.error("Implement init failed")
    }
  }

  const handleCreateProtocol = async () => {
    if (!selectedTasksPath) {
      toast.error("Generate tasks before creating a protocol")
      return
    }
    try {
      const result = await createProtocolFromSpec.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpecPath || undefined,
        tasks_path: selectedTasksPath,
        spec_run_id: selectedSpecRunId ?? undefined,
      })
      if (result.success && result.protocol) {
        toast.success(`Protocol created with ${result.step_count} steps`)
        router.push(`/protocols/${result.protocol.id}`)
      } else {
        toast.error(result.error || "Protocol creation failed")
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Protocol creation failed")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="6xl" className="h-[90vh] p-0 overflow-hidden">
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

          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                {!isInitialized && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <AlertDescription>
                      SpecKit is not initialized.{" "}
                      <Link href={`/projects/${projectId}?wizard=generate-specs`} className="underline">
                        Start with a specification
                      </Link>
                    </AlertDescription>
                  </Alert>
                )}

                {isInitialized && availableSpecs.length === 0 && specsWithTasks.length === 0 && (
                  <Alert className="border-blue-500/50 bg-blue-500/10">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <AlertDescription>
                      No implementation plans found.{" "}
                      <Link href={`/projects/${projectId}?wizard=design-solution`} className="underline">
                        Create a plan first
                      </Link>
                    </AlertDescription>
                  </Alert>
                )}

                <Card className="border-dashed">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                        <span>Specification</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                        <span>Plan</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <div className="flex items-center gap-2">
                        <div className="h-5 w-5 rounded-full bg-purple-500 flex items-center justify-center text-white text-xs font-bold">
                          3
                        </div>
                        <span className="font-medium text-purple-600">Task List</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <div className="h-5 w-5 rounded-full bg-muted flex items-center justify-center text-xs font-bold">
                          4
                        </div>
                        <span>Execution</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <ListTodo className="h-5 w-5" />
                          Select Implementation Plan
                        </CardTitle>
                        <CardDescription>Choose a specification that already has a plan</CardDescription>
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
                          <div className="text-center py-6 text-muted-foreground">
                            <ListTodo className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            <p>No plans available for task generation</p>
                            {specsWithTasks.length > 0 && (
                              <p className="text-sm mt-1">
                                All {specsWithTasks.length} plans already have tasks generated
                              </p>
                            )}
                          </div>
                        )}

                        {specsWithTasks.length > 0 && (
                          <div className="mt-4 pt-4 border-t">
                            <p className="text-sm font-medium mb-2">Specs with existing tasks:</p>
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
                        <CardDescription>Run clarify/checklist/analyze/implement on the selected spec</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setClarifyOpen(true)}
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
                        <CardDescription>Optionally assign generated tasks directly to an execution sprint</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <Select value={targetSprint} onValueChange={setTargetSprint}>
                          <SelectTrigger>
                            <SelectValue placeholder="No execution (create in backlog)" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={noSprintValue}>No execution (create in backlog)</SelectItem>
                            <Separator className="my-1" />
                            {activeSprints.map((sprint) => (
                              <SelectItem key={sprint.id} value={sprint.id.toString()}>
                                <div className="flex items-center gap-2">
                                  <Target className="h-4 w-4 text-purple-500" />
                                  {sprint.name}
                                  <Badge variant={sprint.status === "active" ? "default" : "secondary"}>
                                    {sprint.status}
                                  </Badge>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {activeSprints.length === 0 && (
                          <p className="text-xs text-muted-foreground mt-2">
                            No active or planning executions.{" "}
                            <Link href={`/projects/${projectId}/execution`} className="underline">
                              Create an execution sprint first
                            </Link>
                          </p>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="bg-purple-500/5 border-purple-500/20">
                      <CardContent className="pt-6">
                        <div className="flex items-start gap-4">
                          <Wand2 className="h-6 w-6 text-purple-500 mt-0.5" />
                          <div className="flex-1">
                            <p className="font-medium mb-2">AI-Powered Task Generation</p>
                            <p className="text-sm text-muted-foreground mb-4">
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

          <div className="border-t px-6 py-4 flex justify-between">
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

        <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
          <DialogContent size="xl">
            <DialogHeader>
              <DialogTitle>Clarify Specification</DialogTitle>
              <DialogDescription>
                Add a clarification entry or notes to the selected spec.
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
      </DialogContent>
    </Dialog>
  )
}
