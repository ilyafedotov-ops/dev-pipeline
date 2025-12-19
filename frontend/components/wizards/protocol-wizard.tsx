"use client"

import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { CheckCircle2, FileCode, Settings, PlayCircle, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

interface ProtocolWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type WizardStep = "template" | "configuration" | "review"

const steps: { id: WizardStep; label: string; icon: LucideIcon }[] = [
  { id: "template", label: "Template Selection", icon: FileCode },
  { id: "configuration", label: "Configuration", icon: Settings },
  { id: "review", label: "Review & Launch", icon: PlayCircle },
]

const templates = [
  { id: "onboarding", name: "Onboarding", description: "Initial project analysis and understanding" },
  { id: "feature", name: "Feature Development", description: "Implement a new feature from specifications" },
  { id: "bugfix", name: "Bug Fix", description: "Diagnose and fix reported issues" },
  { id: "refactor", name: "Code Refactor", description: "Improve code structure and quality" },
  { id: "custom", name: "Custom Protocol", description: "Define your own protocol steps" },
]

export function ProtocolWizard({ open, onOpenChange }: ProtocolWizardProps) {
  const [currentStep, setCurrentStep] = useState<WizardStep>("template")
  const [formData, setFormData] = useState({
    template: "",
    name: "",
    description: "",
    autoStart: "false",
  })

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep)

  const handleNext = () => {
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

  const handleFinish = () => {
    toast.success("Protocol created successfully!")
    onOpenChange(false)
    setCurrentStep("template")
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Create New Protocol</DialogTitle>
          <DialogDescription>Configure a protocol execution workflow for your project.</DialogDescription>
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
          {currentStep === "template" && (
            <div className="space-y-4">
              <RadioGroup value={formData.template} onValueChange={(v) => setFormData({ ...formData, template: v })}>
                {templates.map((template) => (
                  <div key={template.id} className="flex items-start space-x-3 rounded-lg border p-4 hover:bg-accent">
                    <RadioGroupItem value={template.id} id={template.id} className="mt-1" />
                    <div className="flex-1">
                      <Label htmlFor={template.id} className="cursor-pointer">
                        <p className="font-medium">{template.name}</p>
                        <p className="text-sm text-muted-foreground">{template.description}</p>
                      </Label>
                    </div>
                  </div>
                ))}
              </RadioGroup>
            </div>
          )}

          {currentStep === "configuration" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="protocolName">Protocol Name *</Label>
                <Input
                  id="protocolName"
                  placeholder="e.g., Feature: User Authentication"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="protocolDescription">Description</Label>
                <Textarea
                  id="protocolDescription"
                  placeholder="Describe what this protocol will accomplish..."
                  rows={4}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Auto-start Execution</Label>
                <RadioGroup
                  value={formData.autoStart}
                  onValueChange={(v) => setFormData({ ...formData, autoStart: v })}
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="true" id="autostart-yes" />
                    <Label htmlFor="autostart-yes" className="cursor-pointer font-normal">
                      Yes, start immediately after creation
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="false" id="autostart-no" />
                    <Label htmlFor="autostart-no" className="cursor-pointer font-normal">
                      No, I&apos;ll start it manually
                    </Label>
                  </div>
                </RadioGroup>
              </div>
            </div>
          )}

          {currentStep === "review" && (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/50 p-4">
                <h3 className="font-medium mb-2">Protocol Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Template:</span>
                    <span>{templates.find((t) => t.id === formData.template)?.name || "Not selected"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Name:</span>
                    <span>{formData.name || "Not set"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Auto-start:</span>
                    <span>{formData.autoStart === "true" ? "Yes" : "No"}</span>
                  </div>
                </div>
              </div>
              <div className="rounded-lg border bg-blue-500/10 p-4">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  The protocol will be created with the selected template. You can monitor its progress from the
                  protocols page.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <Separator />
        <div className="flex justify-between px-6 py-4">
          <Button variant="outline" onClick={handleBack} disabled={currentStepIndex === 0}>
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleNext}>{currentStepIndex === steps.length - 1 ? "Create Protocol" : "Next"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
