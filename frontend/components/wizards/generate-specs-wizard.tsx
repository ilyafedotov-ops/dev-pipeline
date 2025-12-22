"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  FileText,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FolderOpen,
  Loader2,
  ListTodo,
  FileCode,
  Target,
  MessageSquare,
  ClipboardCheck,
  FileSearch,
  PlayCircle,
  ArrowRight,
} from "lucide-react"
import {
  useProject,
  useSpecKitStatus,
  useInitSpecKit,
  useGenerateSpec,
  useClarifySpec,
  useGenerateChecklist,
  useAnalyzeSpec,
  useRunImplement,
} from "@/lib/api"

// Minimum character length for description (matches backend validation)
const MIN_DESCRIPTION_LENGTH = 5

interface GenerateSpecsWizardProps {
  projectId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GenerateSpecsWizardModal({ projectId, open, onOpenChange }: GenerateSpecsWizardProps) {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    featureName: "",
    featureDescription: "",
    requirements: "",
    constraints: "",
  })
  const [lastSpecPath, setLastSpecPath] = useState<string | null>(null)
  const [lastSpecRunId, setLastSpecRunId] = useState<number | null>(null)
  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifyQuestion, setClarifyQuestion] = useState("")
  const [clarifyAnswer, setClarifyAnswer] = useState("")
  const [clarifyNotes, setClarifyNotes] = useState("")

  const { data: project, isLoading: projectLoading } = useProject(projectId)
  const { data: specKitStatus, isLoading: statusLoading, refetch: refetchStatus } = useSpecKitStatus(projectId)

  const initSpecKit = useInitSpecKit()
  const generateSpec = useGenerateSpec()
  const clarifySpec = useClarifySpec()
  const generateChecklist = useGenerateChecklist()
  const analyzeSpec = useAnalyzeSpec()
  const runImplement = useRunImplement()

  const isLoading = projectLoading || statusLoading
  const isInitialized = specKitStatus?.initialized ?? false
  const availableSpecs = useMemo(
    () => (specKitStatus?.specs ?? []).filter((spec) => spec.status !== "cleaned"),
    [specKitStatus],
  )

  const activeSpec = useMemo(() => {
    if (lastSpecRunId) {
      const match = availableSpecs.find((spec) => spec.spec_run_id === lastSpecRunId)
      if (match) return match
    }
    if (lastSpecPath) {
      return availableSpecs.find((spec) => spec.spec_path === lastSpecPath || spec.path === lastSpecPath) || null
    }
    if (!availableSpecs.length) return null
    const sorted = [...availableSpecs].sort((a, b) => {
      const aNum = Number.parseInt(a.name.split("-")[0] || "0", 10)
      const bNum = Number.parseInt(b.name.split("-")[0] || "0", 10)
      return bNum - aNum
    })
    return sorted[0]
  }, [availableSpecs, lastSpecPath, lastSpecRunId])

  const activeSpecPath = activeSpec?.spec_path || null

  const buildFullDescription = () => {
    let desc = formData.featureDescription
    if (formData.requirements) {
      desc += `\n\n## Requirements\n${formData.requirements}`
    }
    if (formData.constraints) {
      desc += `\n\n## Constraints & Considerations\n${formData.constraints}`
    }
    return desc
  }

  // Validation state
  const fullDescription = buildFullDescription()
  const descriptionLength = fullDescription.length
  const isDescriptionValid = descriptionLength >= MIN_DESCRIPTION_LENGTH
  const descriptionError = !isDescriptionValid && formData.featureDescription.length > 0
    ? `Description must be at least ${MIN_DESCRIPTION_LENGTH} characters (currently ${descriptionLength})`
    : null

  const handleInitialize = async () => {
    try {
      const result = await initSpecKit.mutateAsync({ project_id: projectId })
      if (result.success) {
        toast.success("SpecKit initialized successfully!")
        refetchStatus()
      } else {
        toast.error(result.error || "Failed to initialize SpecKit")
      }
    } catch {
      toast.error("Failed to initialize SpecKit")
    }
  }

  const handleNext = () => {
    if (step < 3) setStep(step + 1)
  }

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1)
      return
    }
    onOpenChange(false)
  }

  const handleGenerate = async () => {
    if (!isDescriptionValid) {
      toast.error(`Description must be at least ${MIN_DESCRIPTION_LENGTH} characters`)
      return
    }

    try {
      const result = await generateSpec.mutateAsync({
        project_id: projectId,
        description: fullDescription,
        feature_name: formData.featureName || undefined,
      })

      if (result.success) {
        toast.success(`Specification generated: ${result.feature_name || "Feature"}`)
        if (result.spec_path) {
          setLastSpecPath(result.spec_path)
          setLastSpecRunId(result.spec_run_id ?? null)
          router.push(`/projects/${projectId}?tab=spec&spec=${result.spec_path}`)
        }
        onOpenChange(false)
      } else {
        toast.error(result.error || "Failed to generate specification")
      }
    } catch {
      toast.error("Failed to generate specification")
    }
  }

  const handleClarify = async () => {
    if (!activeSpecPath) {
      toast.error("No spec available to clarify")
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
        spec_path: activeSpecPath,
        entries: hasEntry ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }] : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    if (!activeSpecPath) {
      toast.error("No spec available for checklist")
      return
    }
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    if (!activeSpecPath) {
      toast.error("No spec available for analysis")
      return
    }
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        plan_path: activeSpec?.plan_path || undefined,
        tasks_path: activeSpec?.tasks_path || undefined,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
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
    if (!activeSpecPath) {
      toast.error("No spec available to implement")
      return
    }
    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: activeSpecPath,
        spec_run_id: activeSpec?.spec_run_id ?? undefined,
      })
      if (result.success) {
        toast.success("Implementation run initialized")
      } else {
        toast.error(result.error || "Implementation init failed")
      }
    } catch {
      toast.error("Implementation init failed")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="5xl" className="h-[90vh] max-h-[90vh] p-0 overflow-hidden">
        <div className="flex h-full flex-col min-h-0">
          <DialogHeader className="border-b px-6 py-4 flex-shrink-0">
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-500" />
              Generate Specification
            </DialogTitle>
            <DialogDescription>
              Create a feature spec for {project?.name || "this project"}.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-6 space-y-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                {!isInitialized && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <AlertDescription className="flex items-center justify-between gap-4">
                      <span>
                        SpecKit is not initialized for this project. Initialize it to start generating specifications.
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

                <div className="rounded-lg border bg-muted/30 p-4">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                          }`}
                      >
                        1
                      </div>
                      <span className={step >= 1 ? "font-medium" : "text-muted-foreground"}>Feature Info</span>
                    </div>
                    <Separator className="flex-1 mx-4" />
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                          }`}
                      >
                        2
                      </div>
                      <span className={step >= 2 ? "font-medium" : "text-muted-foreground"}>Details</span>
                    </div>
                    <Separator className="flex-1 mx-4" />
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 3 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                          }`}
                      >
                        3
                      </div>
                      <span className={step >= 3 ? "font-medium" : "text-muted-foreground"}>Generate</span>
                    </div>
                  </div>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>
                      {step === 1 && "Feature Information"}
                      {step === 2 && "Requirements & Constraints"}
                      {step === 3 && "Review & Generate"}
                    </CardTitle>
                    <CardDescription>
                      {step === 1 && "Describe the feature you want to implement"}
                      {step === 2 && "Provide functional requirements and any constraints"}
                      {step === 3 && "Review your inputs and generate the specification"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {step === 1 && (
                      <div className="space-y-6">
                        <div className="space-y-2">
                          <Label htmlFor="featureName">Feature Name *</Label>
                          <Input
                            id="featureName"
                            placeholder="e.g., User Authentication System"
                            value={formData.featureName}
                            onChange={(e) => setFormData({ ...formData, featureName: e.target.value })}
                          />
                          <p className="text-xs text-muted-foreground">A short, descriptive name for this feature</p>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="featureDescription">Description *</Label>
                            <span className={`text-xs ${descriptionError ? 'text-destructive' : 'text-muted-foreground'}`}>
                              {descriptionLength}/{MIN_DESCRIPTION_LENGTH} min characters
                            </span>
                          </div>
                          <Textarea
                            id="featureDescription"
                            placeholder="Describe what this feature should do, who will use it, and what problem it solves..."
                            rows={8}
                            value={formData.featureDescription}
                            onChange={(e) => setFormData({ ...formData, featureDescription: e.target.value })}
                            className={descriptionError ? 'border-destructive' : ''}
                          />
                          {descriptionError && (
                            <p className="text-xs text-destructive">{descriptionError}</p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            Provide a detailed description of the feature. Minimum {MIN_DESCRIPTION_LENGTH} characters required.
                          </p>
                        </div>
                      </div>
                    )}

                    {step === 2 && (
                      <div className="space-y-6">
                        <div className="space-y-2">
                          <Label htmlFor="requirements">Functional Requirements</Label>
                          <Textarea
                            id="requirements"
                            placeholder="List the key requirements, user stories, or acceptance criteria..."
                            rows={8}
                            value={formData.requirements}
                            onChange={(e) => setFormData({ ...formData, requirements: e.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="constraints">Constraints & Considerations</Label>
                          <Textarea
                            id="constraints"
                            placeholder="Any technical constraints, security requirements, performance targets..."
                            rows={5}
                            value={formData.constraints}
                            onChange={(e) => setFormData({ ...formData, constraints: e.target.value })}
                          />
                        </div>
                      </div>
                    )}

                    {step === 3 && (
                      <div className="space-y-6">
                        <div className="grid gap-6 md:grid-cols-2">
                          <Card className="border-2">
                            <CardHeader>
                              <CardTitle className="text-base flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                Feature Summary
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                              <div>
                                <p className="text-sm font-medium text-muted-foreground">Name</p>
                                <p className="font-medium">{formData.featureName}</p>
                              </div>
                              <div>
                                <p className="text-sm font-medium text-muted-foreground">Project</p>
                                <p className="text-sm">{project?.name}</p>
                              </div>
                            </CardContent>
                          </Card>

                          <Card className="border-2">
                            <CardHeader>
                              <CardTitle className="text-base flex items-center gap-2">
                                <Sparkles className="h-4 w-4" />
                                What SpecKit Will Generate
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                              <div className="flex items-center justify-between">
                                <span className="text-sm flex items-center gap-2">
                                  <FileCode className="h-4 w-4 text-blue-500" />
                                  Feature Specification (spec.md)
                                </span>
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                              </div>
                              <Separator />
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Target className="h-3 w-3" />
                                <span>Next: Plan → Tasks → Execution</span>
                              </div>
                            </CardContent>
                          </Card>
                        </div>

                        <Card className="bg-muted/50">
                          <CardHeader>
                            <CardTitle className="text-base">Description Preview</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-muted-foreground whitespace-pre-wrap max-h-48 overflow-y-auto">
                              {buildFullDescription() || "No description provided"}
                            </p>
                          </CardContent>
                        </Card>

                        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <Sparkles className="h-5 w-5 text-blue-500 mt-0.5" />
                            <div>
                              <p className="font-medium mb-1">AI-Powered Generation</p>
                              <p className="text-sm text-muted-foreground">
                                SpecKit will analyze your description and generate a detailed technical specification.
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
                    <CardDescription>Run clarify/checklist/analyze/implement on the latest spec</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {activeSpecPath ? (
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={() => setClarifyOpen(true)}>
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
                      <p className="text-sm text-muted-foreground">Generate a specification to unlock actions.</p>
                    )}
                  </CardContent>
                </Card>

                {isInitialized && specKitStatus && specKitStatus.spec_count > 0 && (
                  <Card className="border-dashed">
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
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
                          <div key={spec.path} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
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

          <div className="border-t px-6 py-4 flex justify-between flex-shrink-0">
            <Button variant="outline" onClick={handleBack}>
              {step === 1 ? "Cancel" : "Back"}
            </Button>
            {step < 3 ? (
              <Button onClick={handleNext} disabled={!formData.featureName || !isDescriptionValid}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleGenerate} disabled={generateSpec.isPending || !isInitialized || !isDescriptionValid}>
                {generateSpec.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate Specification
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
          <DialogContent size="xl">
            <DialogHeader>
              <DialogTitle>Clarify Specification</DialogTitle>
              <DialogDescription>Add a clarification entry or notes to the latest spec.</DialogDescription>
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
