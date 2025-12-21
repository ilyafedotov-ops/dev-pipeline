"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Lightbulb,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ClipboardList,
  Layers,
  Database,
  Network,
  ArrowRight,
  MessageSquare,
  ClipboardCheck,
  FileSearch,
  PlayCircle,
} from "lucide-react"
import {
  useProject,
  useSpecKitStatus,
  useGeneratePlan,
  useProjectSpecs,
  useClarifySpec,
  useGenerateChecklist,
  useAnalyzeSpec,
  useRunImplement,
} from "@/lib/api"

interface DesignSolutionWizardProps {
  projectId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DesignSolutionWizardModal({ projectId, open, onOpenChange }: DesignSolutionWizardProps) {
  const router = useRouter()
  const { data: project, isLoading: projectLoading } = useProject(projectId)
  const { data: specKitStatus, isLoading: statusLoading } = useSpecKitStatus(projectId)
  const { data: specs, isLoading: specsLoading } = useProjectSpecs(projectId)

  const generatePlan = useGeneratePlan()
  const clarifySpec = useClarifySpec()
  const generateChecklist = useGenerateChecklist()
  const analyzeSpec = useAnalyzeSpec()
  const runImplement = useRunImplement()

  const [selectedSpec, setSelectedSpec] = useState<string>("")
  const [additionalContext, setAdditionalContext] = useState("")
  const [generatedPlanPath, setGeneratedPlanPath] = useState<string | null>(null)
  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifyQuestion, setClarifyQuestion] = useState("")
  const [clarifyAnswer, setClarifyAnswer] = useState("")
  const [clarifyNotes, setClarifyNotes] = useState("")

  const isLoading = projectLoading || statusLoading || specsLoading
  const isInitialized = specKitStatus?.initialized ?? false
  const availableSpecs =
    specs?.filter((s) => s.status !== "cleaned" && s.has_spec && !!s.spec_path && !s.has_plan) || []
  const specsWithPlans = specs?.filter((s) => s.status !== "cleaned" && s.has_plan) || []
  const selectedSpecMeta = useMemo(
    () => specs?.find((spec) => spec.spec_path === selectedSpec) || null,
    [specs, selectedSpec],
  )
  const selectedSpecPath = selectedSpec || selectedSpecMeta?.spec_path || ""
  const selectedPlanPath = selectedSpecMeta?.plan_path || generatedPlanPath || null
  const selectedTasksPath = selectedSpecMeta?.tasks_path || null
  const selectedSpecRunId = selectedSpecMeta?.spec_run_id ?? null

  const handleGenerate = async () => {
    if (!selectedSpec) {
      toast.error("Please select a specification to generate a plan for")
      return
    }

    try {
      const result = await generatePlan.mutateAsync({
        project_id: projectId,
        spec_path: selectedSpec,
        context: additionalContext || undefined,
        spec_run_id: selectedSpecRunId ?? undefined,
      })

      if (result.success) {
        toast.success("Implementation plan generated successfully!")
        if (result.plan_path) {
          setGeneratedPlanPath(result.plan_path)
          router.push(`/projects/${projectId}?tab=spec&plan=${result.plan_path}`)
        }
        onOpenChange(false)
      } else {
        toast.error(result.error || "Failed to generate implementation plan")
      }
    } catch {
      toast.error("Failed to generate implementation plan")
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
        plan_path: selectedPlanPath || undefined,
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="5xl" className="h-[90vh] p-0 overflow-hidden">
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
                      SpecKit is not initialized for this project. {" "}
                      <Link href={`/projects/${projectId}?wizard=generate-specs`} className="underline">
                        Initialize it first
                      </Link>{" "}
                      to generate specifications.
                    </AlertDescription>
                  </Alert>
                )}

                {isInitialized && availableSpecs.length === 0 && specs?.length === 0 && (
                  <Alert className="border-blue-500/50 bg-blue-500/10">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <AlertDescription>
                      No specifications found. {" "}
                      <Link href={`/projects/${projectId}?wizard=generate-specs`} className="underline">
                        Generate a specification first
                      </Link>{" "}
                      before creating an implementation plan.
                    </AlertDescription>
                  </Alert>
                )}

                <Card className="border-dashed">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                        <span className="font-medium">Specification</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <div className="flex items-center gap-2">
                        <div className="h-5 w-5 rounded-full bg-amber-500 flex items-center justify-center text-white text-xs font-bold">
                          2
                        </div>
                        <span className="font-medium text-amber-600">Implementation Plan</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <div className="h-5 w-5 rounded-full bg-muted flex items-center justify-center text-xs font-bold">
                          3
                        </div>
                        <span>Task List</span>
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
                        <div className="text-center py-6 text-muted-foreground">
                          <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p>No specifications available for plan generation</p>
                          {specsWithPlans.length > 0 && (
                            <p className="text-sm mt-1">
                              All {specsWithPlans.length} specs already have plans generated
                            </p>
                          )}
                        </div>
                      )}

                      {specsWithPlans.length > 0 && (
                        <div className="mt-4 pt-4 border-t">
                          <p className="text-sm font-medium mb-2">Specs with existing plans:</p>
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
                        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
                          <Layers className="h-5 w-5 text-amber-500 mt-0.5" />
                          <div>
                            <p className="font-medium">Implementation Plan</p>
                            <p className="text-xs text-muted-foreground">
                              Step-by-step implementation guide with phases and milestones
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
                          <Database className="h-5 w-5 text-blue-500 mt-0.5" />
                          <div>
                            <p className="font-medium">Data Model</p>
                            <p className="text-xs text-muted-foreground">
                              Database schema and entity relationships
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
                          <Network className="h-5 w-5 text-green-500 mt-0.5" />
                          <div>
                            <p className="font-medium">API Contracts</p>
                            <p className="text-xs text-muted-foreground">
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
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </div>

          <div className="border-t px-6 py-4 flex justify-between">
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

        <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
          <DialogContent size="xl">
            <DialogHeader>
              <DialogTitle>Clarify Specification</DialogTitle>
              <DialogDescription>Add a clarification entry or notes to the selected spec.</DialogDescription>
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
