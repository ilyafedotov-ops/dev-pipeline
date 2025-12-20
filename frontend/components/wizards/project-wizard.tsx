"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, GitBranch, Settings, Shield, HelpCircle, type LucideIcon, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { useCreateProject, useUpdateProjectPolicy, useStartOnboarding } from "@/lib/api/hooks/use-projects"

interface ProjectWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type WizardStep = "git" | "classification" | "policy" | "clarifications" | "onboarding"

const steps: { id: WizardStep; label: string; icon: LucideIcon }[] = [
  { id: "git", label: "Git Repository", icon: GitBranch },
  { id: "classification", label: "Classification", icon: Settings },
  { id: "policy", label: "Policy Pack", icon: Shield },
  { id: "clarifications", label: "Clarifications", icon: HelpCircle },
  { id: "onboarding", label: "Onboarding", icon: CheckCircle2 },
]

export function ProjectWizard({ open, onOpenChange }: ProjectWizardProps) {
  const router = useRouter()
  const createProject = useCreateProject()
  const updatePolicy = useUpdateProjectPolicy()
  const startOnboarding = useStartOnboarding()

  const [currentStep, setCurrentStep] = useState<WizardStep>("git")
  const [formData, setFormData] = useState({
    repoUrl: "",
    branch: "main",
    classification: "",
    description: "",
    policyPack: "",
    enforcementMode: "advisory",
  })
  const [clarifications, setClarifications] = useState([
    { id: "1", question: "What is the primary programming language?", answer: "" },
    { id: "2", question: "Does this project use a database?", answer: "" },
    { id: "3", question: "What testing framework is preferred?", answer: "" },
  ])
  const [isSubmitting, setIsSubmitting] = useState(false)

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep)

  const handleNext = () => {
    // Validation
    if (currentStep === "git") {
      if (!formData.repoUrl) {
        toast.error("Repository URL is required")
        return
      }
    }

    const nextIndex = currentStepIndex + 1
    if (nextIndex < steps.length) {
      setCurrentStep(steps[nextIndex].id)
    } else {
      handleFinish()
    }
  }

  const handleBack = () => {
    const prevIndex = currentStepIndex - 1
    if (prevIndex >= 0) {
      setCurrentStep(steps[prevIndex].id)
    }
  }

  const extractProjectName = (url: string) => {
    try {
      const parts = url.split("/")
      let name = parts[parts.length - 1]
      if (name.endsWith(".git")) {
        name = name.slice(0, -4)
      }
      return name || "untitled-project"
    } catch (e) {
      return "untitled-project"
    }
  }

  const handleFinish = async () => {
    setIsSubmitting(true)
    try {
      const name = extractProjectName(formData.repoUrl)

      let finalDescription = formData.description

      // Append Classification
      if (formData.classification) {
        finalDescription += `\n\nClassification: ${formData.classification}`
      }

      // Append Clarifications
      const answeredClarifications = clarifications.filter(c => c.answer && c.answer.trim())
      if (answeredClarifications.length > 0) {
        finalDescription += `\n\nInitial Clarifications:\n`
        answeredClarifications.forEach(c => {
          finalDescription += `- ${c.question}: ${c.answer}\n`
        })
      }

      // 1. Create Project
      const project = await createProject.mutateAsync({
        name,
        git_url: formData.repoUrl,
        base_branch: formData.branch || "main",
        description: finalDescription,
      })

      // 2. Update Policy if selected
      if (formData.policyPack || formData.enforcementMode) {
        await updatePolicy.mutateAsync({
          projectId: project.id,
          policy: {
            policy_pack_key: formData.policyPack || undefined,
            policy_enforcement_mode: formData.enforcementMode || undefined,
          },
        })
      }

      // 3. Start Onboarding
      await startOnboarding.mutateAsync(project.id)

      toast.success("Project created and onboarding started!")
      onOpenChange(false)
      setCurrentStep("git")
      setFormData({
        repoUrl: "",
        branch: "main",
        classification: "",
        description: "",
        policyPack: "",
        enforcementMode: "advisory",
      })
      setClarifications([
        { id: "1", question: "What is the primary programming language?", answer: "" },
        { id: "2", question: "Does this project use a database?", answer: "" },
        { id: "3", question: "What testing framework is preferred?", answer: "" },
      ])

      // Redirect to the new project
      router.push(`/projects/${project.id}/onboarding`)
    } catch (error) {
      console.error(error)
      toast.error("Failed to create project")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="3xl" className="max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>Follow the steps to set up your project with TasksGodzilla.</DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center justify-between px-4 py-6">
          {steps.map((step, index) => {
            const Icon = step.icon
            const isCompleted = index < currentStepIndex
            const isCurrent = step.id === currentStep
            return (
              <div key={step.id} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                      isCompleted && "border-primary bg-primary text-primary-foreground",
                      isCurrent && "border-primary text-primary",
                      !isCompleted && !isCurrent && "border-muted text-muted-foreground",
                    )}
                  >
                    {isCompleted ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                  </div>
                  <span className={cn("text-xs font-medium", isCurrent ? "text-foreground" : "text-muted-foreground")}>
                    {step.label}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={cn("flex-1 border-t-2 mx-2", isCompleted ? "border-primary" : "border-muted")} />
                )}
              </div>
            )
          })}
        </div>

        <Separator />

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {currentStep === "git" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="repoUrl">Repository URL *</Label>
                <Input
                  id="repoUrl"
                  placeholder="https://github.com/username/repo.git"
                  value={formData.repoUrl}
                  onChange={(e) => setFormData({ ...formData, repoUrl: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Enter the Git repository URL for your project</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="branch">Default Branch</Label>
                <Input
                  id="branch"
                  placeholder="main"
                  value={formData.branch}
                  onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                />
              </div>
            </div>
          )}

          {currentStep === "classification" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="classification">Project Classification *</Label>
                <Select
                  value={formData.classification}
                  onValueChange={(v) => setFormData({ ...formData, classification: v })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select classification" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="web-app">Web Application</SelectItem>
                    <SelectItem value="api">API Service</SelectItem>
                    <SelectItem value="mobile">Mobile App</SelectItem>
                    <SelectItem value="library">Library/Package</SelectItem>
                    <SelectItem value="data-pipeline">Data Pipeline</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Describe your project..."
                  rows={4}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
            </div>
          )}

          {currentStep === "policy" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="policyPack">Policy Pack</Label>
                <Select value={formData.policyPack} onValueChange={(v) => setFormData({ ...formData, policyPack: v })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a policy pack" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default Policy Pack</SelectItem>
                    <SelectItem value="strict">Strict Enforcement</SelectItem>
                    <SelectItem value="security">Security Focused</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">Choose a policy pack to enforce coding standards</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="enforcementMode">Enforcement Mode</Label>
                <Select
                  value={formData.enforcementMode}
                  onValueChange={(v) => setFormData({ ...formData, enforcementMode: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="advisory">Advisory (Warnings only)</SelectItem>
                    <SelectItem value="mandatory">Mandatory (Block on violations)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {currentStep === "clarifications" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Answer these questions to help TasksGodzilla better understand your project
              </p>
              {clarifications.map((clarification) => (
                <div key={clarification.id} className="space-y-2">
                  <Label>{clarification.question}</Label>
                  <Textarea
                    placeholder="Your answer..."
                    rows={2}
                    value={clarification.answer}
                    onChange={(e) => {
                      setClarifications(
                        clarifications.map((c) => (c.id === clarification.id ? { ...c, answer: e.target.value } : c)),
                      )
                    }}
                  />
                </div>
              ))}
            </div>
          )}

          {currentStep === "onboarding" && (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/50 p-4">
                <h3 className="font-medium mb-2">Project Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Repository:</span>
                    <span className="font-mono text-xs">{formData.repoUrl || "Not set"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Branch:</span>
                    <span>{formData.branch}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Classification:</span>
                    <Badge variant="secondary">{formData.classification || "Not set"}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Policy Pack:</span>
                    <span>{formData.policyPack || "None"}</span>
                  </div>
                </div>
              </div>
              <div className="rounded-lg border bg-blue-500/10 p-4">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  After creating the project, the onboarding process will begin. You may need to answer clarification
                  questions to help TasksGodzilla understand your codebase.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <Separator />
        <div className="flex justify-between px-6 py-4">
          <Button variant="outline" onClick={handleBack} disabled={currentStepIndex === 0 || isSubmitting}>
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleNext} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {currentStepIndex === steps.length - 1 ? "Create Project" : "Next"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
