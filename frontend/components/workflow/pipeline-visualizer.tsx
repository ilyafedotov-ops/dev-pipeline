"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { StatusPill } from "@/components/ui/status-pill"
import { Play, Pause, CheckCircle, XCircle, Clock, Bot, ArrowRight, Settings, Maximize2, Download } from "lucide-react"
import { cn } from "@/lib/utils"
import type { StepRun, ProtocolRun } from "@/lib/api/types"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useState } from "react"
import { toast } from "sonner"

interface PipelineVisualizerProps {
  protocol: ProtocolRun
  steps: StepRun[]
  onStepClick?: (step: StepRun) => void
  onAssignAgent?: (stepId: number, agentId: string) => void
}

const availableAgents = [
  { id: "claude-sonnet-4", name: "Claude Sonnet 4", provider: "Anthropic", speed: "fast" },
  { id: "gpt-4o", name: "GPT-4o", provider: "OpenAI", speed: "fast" },
  { id: "gemini-2-flash", name: "Gemini 2.0 Flash", provider: "Google", speed: "very-fast" },
  { id: "grok-4", name: "Grok 4", provider: "xAI", speed: "fast" },
  { id: "llama-4-70b", name: "Llama 4 70B", provider: "Meta", speed: "medium" },
  { id: "mistral-large", name: "Mistral Large", provider: "Mistral", speed: "fast" },
]

export function PipelineVisualizer({ protocol, steps, onStepClick, onAssignAgent }: PipelineVisualizerProps) {

  const getStepIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case "running":
        return <Play className="h-5 w-5 text-blue-500 animate-pulse" />
      case "failed":
        return <XCircle className="h-5 w-5 text-red-500" />
      case "cancelled":
        return <XCircle className="h-5 w-5 text-gray-500" />
      case "paused":
        return <Pause className="h-5 w-5 text-yellow-500" />
      default:
        return <Clock className="h-5 w-5 text-muted-foreground" />
    }
  }

  const content = (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Workflow Pipeline</h3>
          <p className="text-sm text-muted-foreground">
            {steps.filter((s) => s.status === "completed").length} / {steps.length} steps completed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Maximize2 className="h-4 w-4 mr-2" />
                Fullscreen
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-7xl h-[90vh]">
              <DialogHeader>
                <DialogTitle>Pipeline Workflow - {protocol.protocol_name}</DialogTitle>
                <DialogDescription>Full workflow visualization with agent assignments</DialogDescription>
              </DialogHeader>
              <div className="overflow-auto h-full">
                <PipelineVisualizer
                  protocol={protocol}
                  steps={steps}
                  onStepClick={onStepClick}
                  onAssignAgent={onAssignAgent}
                />
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="relative">
        <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-border" />

        <div className="space-y-4">
          {steps.map((step, index) => (
            <div key={step.id} className="relative">
              <div
                className={cn(
                  "flex items-start gap-4 p-4 rounded-lg border-2 transition-all cursor-pointer hover:border-primary/50",
                  step.status === "running" && "border-blue-500/50 bg-blue-500/5",
                  step.status === "completed" && "border-green-500/30 bg-green-500/5",
                  step.status === "failed" && "border-red-500/50 bg-red-500/5",
                  step.status === "pending" && "border-border bg-card",
                )}
                onClick={() => onStepClick?.(step)}
              >
                <div className="relative z-10 flex-shrink-0">{getStepIcon(step.status)}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <Badge variant="outline" className="text-xs font-mono">
                          Step {step.step_index}
                        </Badge>
                        <h4 className="font-semibold truncate">{step.step_name}</h4>
                        <StatusPill status={step.status} size="sm" />
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                        <span className="capitalize">Type: {step.step_type}</span>
                        {step.model && (
                          <>
                            <span>•</span>
                            <span>Model: {step.model}</span>
                          </>
                        )}
                        {step.retries > 0 && (
                          <>
                            <span>•</span>
                            <span className="text-yellow-600">Retries: {step.retries}</span>
                          </>
                        )}
                      </div>

                      {step.summary && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{step.summary}</p>
                      )}

                      <AssignAgentButton stepId={step.id} currentAgent={step.engine_id} onAssign={onAssignAgent} />
                    </div>
                  </div>
                </div>
              </div>

              {index < steps.length - 1 && (
                <div className="flex items-center justify-center py-2">
                  <ArrowRight className="h-5 w-5 text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  if (fullscreen) {
    return content
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Workflow Pipeline</CardTitle>
        <CardDescription>Visual representation of the protocol execution pipeline</CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

function AssignAgentButton({
  stepId,
  currentAgent,
  onAssign,
}: {
  stepId: number
  currentAgent: string | null
  onAssign?: (stepId: number, agentId: string) => void
}) {
  const [selectedAgent, setSelectedAgent] = useState(currentAgent || "")
  const [open, setOpen] = useState(false)

  const handleAssign = () => {
    if (selectedAgent && onAssign) {
      onAssign(stepId, selectedAgent)
      toast.success(`Agent ${selectedAgent} assigned to step`)
      setOpen(false)
    }
  }

  const currentAgentInfo = availableAgents.find((a) => a.id === currentAgent)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 bg-transparent">
          <Bot className="h-3.5 w-3.5" />
          {currentAgentInfo ? (
            <span className="text-xs">
              {currentAgentInfo.name} ({currentAgentInfo.provider})
            </span>
          ) : (
            <span className="text-xs">Assign Agent</span>
          )}
          <Settings className="h-3 w-3 ml-1" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign AI Agent</DialogTitle>
          <DialogDescription>Select an AI agent to execute this workflow step</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="agent">AI Agent</Label>
            <Select value={selectedAgent} onValueChange={setSelectedAgent}>
              <SelectTrigger id="agent">
                <SelectValue placeholder="Select an agent" />
              </SelectTrigger>
              <SelectContent>
                {availableAgents.map((agent) => (
                  <SelectItem key={agent.id} value={agent.id}>
                    <div className="flex items-center justify-between gap-3 w-full">
                      <span className="font-medium">{agent.name}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">
                          {agent.provider}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-xs",
                            agent.speed === "very-fast" && "border-green-500 text-green-600",
                            agent.speed === "fast" && "border-blue-500 text-blue-600",
                            agent.speed === "medium" && "border-yellow-500 text-yellow-600",
                          )}
                        >
                          {agent.speed}
                        </Badge>
                      </div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedAgent && (
            <div className="p-3 bg-muted rounded-lg space-y-2">
              <p className="text-sm font-medium">Agent Details</p>
              {availableAgents
                .filter((a) => a.id === selectedAgent)
                .map((agent) => (
                  <div key={agent.id} className="text-xs text-muted-foreground space-y-1">
                    <p>Provider: {agent.provider}</p>
                    <p>Speed: {agent.speed}</p>
                  </div>
                ))}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleAssign} disabled={!selectedAgent}>
            Assign Agent
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
