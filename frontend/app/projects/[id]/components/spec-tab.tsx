"use client"

import { useState } from "react"
import Link from "next/link"
import {
  useProject,
  useSpecKitStatus,
  useSpecifications,
  useClarifySpec,
  useGenerateChecklist,
  useAnalyzeSpec,
  useRunImplement,
  useGenerateSpec,
} from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { LoadingState } from "@/components/ui/loading-state"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  RefreshCw,
  Download,
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  ClipboardCheck,
  Sparkles,
  MessageSquare,
  FileSearch,
  PlayCircle,
  RotateCcw,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"

interface SpecTabProps {
  projectId: number
}

const LAST_UPDATED_BASE = Date.now()

export function SpecTab({ projectId }: SpecTabProps) {
  const { data: project, isLoading: projectLoading } = useProject(projectId)
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useSpecKitStatus(projectId)
  const { data: specs, isLoading: specsLoading, refetch: refetchSpecs } = useSpecifications({ project_id: projectId })
  const clarifySpec = useClarifySpec()
  const generateChecklist = useGenerateChecklist()
  const analyzeSpec = useAnalyzeSpec()
  const runImplement = useRunImplement()
  const generateSpec = useGenerateSpec()

  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifySpecPath, setClarifySpecPath] = useState<string | null>(null)
  const [clarifySpecRunId, setClarifySpecRunId] = useState<number | null>(null)
  const [clarifyQuestion, setClarifyQuestion] = useState("")
  const [clarifyAnswer, setClarifyAnswer] = useState("")
  const [clarifyNotes, setClarifyNotes] = useState("")

  const isLoading = projectLoading || statusLoading || specsLoading

  if (isLoading) return <LoadingState message="Loading specification..." />

  // Handle uninitialized SpecKit
  if (!status?.initialized) {
    return (
      <div className="space-y-6">
        <div className="text-center py-12">
          <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">SpecKit Not Initialized</h3>
          <p className="text-sm text-muted-foreground mb-4">
            This project hasn&apos;t been initialized with SpecKit yet.
          </p>
          <p className="text-sm text-muted-foreground">
            Use the CLI to initialize: <code className="bg-muted px-2 py-1 rounded">devgodzilla spec init</code>
          </p>
        </div>
      </div>
    )
  }

  const handleRefresh = () => {
    refetchStatus()
    refetchSpecs()
  }

  const handleClarify = async () => {
    if (!clarifySpecPath) {
      toast.error("Select a spec to clarify")
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
        spec_path: clarifySpecPath,
        entries: hasEntry ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }] : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
        spec_run_id: clarifySpecRunId ?? undefined,
      })

      if (result.success) {
        toast.success(`Clarifications added (${result.clarifications_added})`)
        setClarifyOpen(false)
        setClarifyQuestion("")
        setClarifyAnswer("")
        setClarifyNotes("")
        setClarifySpecRunId(null)
      } else {
        toast.error(result.error || "Failed to add clarifications")
      }
    } catch {
      toast.error("Failed to add clarifications")
    }
  }

  const handleChecklist = async (specPath: string, specRunId?: number | null) => {
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
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

  const handleAnalyze = async (
    specPath: string,
    planPath?: string | null,
    tasksPath?: string | null,
    specRunId?: number | null,
  ) => {
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        plan_path: planPath || undefined,
        tasks_path: tasksPath || undefined,
        spec_run_id: specRunId ?? undefined,
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

  const handleImplement = async (specPath: string, specRunId?: number | null) => {
    try {
      const result = await runImplement.mutateAsync({
        project_id: projectId,
        spec_path: specPath,
        spec_run_id: specRunId ?? undefined,
      })
      if (result.success) {
        toast.success("Implementation run initialized")
      } else {
        toast.error(result.error || "Implement initialization failed")
      }
    } catch {
      toast.error("Implement initialization failed")
    }
  }

  const handleRetry = async (featureName: string, specName?: string | null) => {
    // Use spec name or feature name as description for retry
    const description = specName || featureName || "Retry specification"
    try {
      toast.info("Retrying specification generation...")
      const result = await generateSpec.mutateAsync({
        project_id: projectId,
        description,
        feature_name: featureName,
      })
      if (result.success) {
        toast.success(`Spec regenerated: ${result.feature_name}`)
        refetchSpecs()
        refetchStatus()
      } else {
        toast.error(result.error || "Retry failed")
      }
    } catch {
      toast.error("Retry failed")
    }
  }

  const handleExport = () => {
    if (!status || !specs) return

    const exportData = {
      project_id: projectId,
      project_name: project?.name,
      generated_at: new Date().toISOString(),
      constitution: {
        version: status.constitution_version,
        hash: status.constitution_hash
      },
      specifications: specs
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `project-${projectId}-specs.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Get status badge for a specification
  const getStatusBadge = (spec: { has_tasks?: boolean; has_plan?: boolean; status?: string }) => {
    if (spec.status === "cleaned") {
      return (
        <Badge variant="default" className="bg-zinc-500/10 text-zinc-600 hover:bg-zinc-500/20">
          <CheckCircle className="mr-1 h-3 w-3" />
          Cleaned
        </Badge>
      )
    }
    if (spec.status === "failed") {
      return (
        <Badge variant="default" className="bg-red-500/10 text-red-500 hover:bg-red-500/20">
          <AlertCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    }
    if (spec.has_tasks || spec.status === "completed") {
      return (
        <Badge variant="default" className="bg-green-500/10 text-green-500 hover:bg-green-500/20">
          <CheckCircle className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      )
    }
    if (spec.has_plan || spec.status === "in-progress") {
      return (
        <Badge variant="default" className="bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20">
          <Clock className="mr-1 h-3 w-3" />
          In Progress
        </Badge>
      )
    }
    return (
      <Badge variant="default" className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20">
        <FileText className="mr-1 h-3 w-3" />
        Draft
      </Badge>
    )
  }

  // Get last updated date from most recent spec
  const getLastUpdated = () => {
    if (!specs || specs.length === 0) return "No specs yet"
    const dates = specs
      .filter(s => s.created_at)
      .map(s => new Date(s.created_at!))
      .sort((a, b) => b.getTime() - a.getTime())
    if (dates.length === 0) return "Unknown"
    const diff = LAST_UPDATED_BASE - dates[0].getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    if (hours < 1) return "Less than an hour ago"
    if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
    const days = Math.floor(hours / 24)
    return `${days} day${days === 1 ? "" : "s"} ago`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Project Specification</h3>
          <p className="text-sm text-muted-foreground">Technical specification and architecture documentation</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" asChild>
            <Link href={`/projects/${projectId}?wizard=generate-specs&tab=spec`}>
              <Sparkles className="mr-2 h-4 w-4" />
              Launch SpecKit Wizard
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
              <p className="text-sm font-medium text-muted-foreground">Constitution Version</p>
              <p className="text-lg font-semibold">
                {status.constitution_version || "Not set"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Specifications</p>
              <p className="text-lg font-semibold">{status.spec_count} defined</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Last Updated</p>
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
            <div className="flex justify-between items-center">
              <span className="text-sm">Initialized</span>
              <Badge variant="default" className="bg-green-500/10 text-green-500">
                <CheckCircle className="mr-1 h-3 w-3" />
                Yes
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Constitution Hash</span>
              <span className="text-sm font-mono text-muted-foreground truncate max-w-[150px]" title={status.constitution_hash || undefined}>
                {status.constitution_hash ? status.constitution_hash.slice(0, 12) + "..." : "N/A"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Total Specs</span>
              <span className="text-sm font-mono text-muted-foreground">{status.spec_count}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Specifications</CardTitle>
          <CardDescription>Feature specifications and implementation status</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(!specs || specs.length === 0) ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="mx-auto h-8 w-8 mb-2 opacity-50" />
              <p className="text-sm">No specifications yet.</p>
              <p className="text-xs mt-1">
                Generate one with: <code className="bg-muted px-2 py-0.5 rounded">devgodzilla spec specify</code>
              </p>
            </div>
          ) : (
            specs.map((spec) => {
              const isCleaned = spec.status === "cleaned"
              const isFailed = spec.status === "failed"
              const specPath = spec.spec_path || spec.path || ""
              return (
                <div key={spec.id} className={`border rounded-lg p-4 space-y-2 ${isFailed ? "border-red-500/50 bg-red-500/5" : ""}`}>
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">{spec.title}</h4>
                    {getStatusBadge(spec)}
                  </div>
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p>
                      <span className="font-medium">Path:</span>{" "}
                      <code className="bg-muted px-1.5 py-0.5 rounded text-xs">{spec.path}</code>
                    </p>
                    <div className="flex gap-4">
                      <span>
                        <span className="font-medium">Plan:</span>{" "}
                        {spec.has_plan ? "✓" : "—"}
                      </span>
                      <span>
                        <span className="font-medium">Tasks:</span>{" "}
                        {spec.has_tasks ? "✓" : "—"}
                      </span>
                      {spec.linked_tasks > 0 && (
                        <span>
                          <span className="font-medium">Linked:</span>{" "}
                          {spec.completed_tasks}/{spec.linked_tasks} tasks
                        </span>
                      )}
                    </div>
                    {isFailed && spec.error_message && (
                      <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded text-red-600 text-xs">
                        <span className="font-medium">Error:</span> {spec.error_message}
                      </div>
                    )}
                    {isFailed && spec.protocol_id && (
                      <div className="mt-1">
                        <Link
                          href={`/protocols/${spec.protocol_id}`}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          View protocol run for details →
                        </Link>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2">
                    {isFailed && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRetry(spec.feature_name || spec.title, spec.title)}
                        disabled={generateSpec.isPending}
                      >
                        <RotateCcw className="mr-2 h-3.5 w-3.5" />
                        {generateSpec.isPending ? "Retrying..." : "Retry"}
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (!specPath) return
                        setClarifySpecPath(specPath)
                        setClarifySpecRunId(spec.spec_run_id ?? null)
                        setClarifyOpen(true)
                      }}
                      disabled={!specPath || isCleaned || isFailed}
                    >
                      <MessageSquare className="mr-2 h-3.5 w-3.5" />
                      Clarify
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleChecklist(specPath, spec.spec_run_id)}
                      disabled={!specPath || isCleaned || isFailed}
                    >
                      <ClipboardCheck className="mr-2 h-3.5 w-3.5" />
                      Checklist
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        handleAnalyze(specPath, spec.plan_path, spec.tasks_path, spec.spec_run_id)
                      }
                      disabled={!specPath || isCleaned || isFailed}
                    >
                      <FileSearch className="mr-2 h-3.5 w-3.5" />
                      Analyze
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleImplement(specPath, spec.spec_run_id)}
                      disabled={!specPath || isCleaned || isFailed}
                    >
                      <PlayCircle className="mr-2 h-3.5 w-3.5" />
                      Implement
                    </Button>
                  </div>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SpecKit Actions</CardTitle>
          <CardDescription>Run clarification, checklist, analysis, and implementation steps</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(!status?.specs || status.specs.length === 0) ? (
            <div className="text-center py-6 text-muted-foreground">
              <FileText className="mx-auto h-8 w-8 mb-2 opacity-50" />
              <p className="text-sm">No spec artifacts available yet.</p>
            </div>
          ) : (
            status.specs.map((spec, index) => {
              const isCleaned = spec.status === "cleaned"
              const specPath = spec.spec_path || spec.path || ""
              const uniqueKey = specPath || spec.name || `spec-${index}`
              return (
                <div key={uniqueKey} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div>
                      <p className="font-medium">{spec.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {specPath}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          if (!specPath) return
                          setClarifySpecPath(specPath)
                          setClarifySpecRunId(spec.spec_run_id ?? null)
                          setClarifyOpen(true)
                        }}
                        disabled={!specPath || isCleaned}
                      >
                        <MessageSquare className="mr-2 h-3.5 w-3.5" />
                        Clarify
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleChecklist(specPath, spec.spec_run_id)}
                        disabled={!specPath || isCleaned}
                      >
                        <ClipboardCheck className="mr-2 h-3.5 w-3.5" />
                        Checklist
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          handleAnalyze(specPath, spec.plan_path, spec.tasks_path, spec.spec_run_id)
                        }
                        disabled={!specPath || isCleaned}
                      >
                        <FileSearch className="mr-2 h-3.5 w-3.5" />
                        Analyze
                      </Button>
                      <Button
                        size="sm"
                        variant="default"
                        onClick={() => handleImplement(specPath, spec.spec_run_id)}
                        disabled={!specPath || isCleaned}
                      >
                        <PlayCircle className="mr-2 h-3.5 w-3.5" />
                        Implement
                      </Button>
                    </div>
                  </div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Plan: {spec.has_plan ? "✓" : "—"}</span>
                    <span>Tasks: {spec.has_tasks ? "✓" : "—"}</span>
                  </div>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Clarify Specification</DialogTitle>
            <DialogDescription>
              Add a clarification entry or free-form notes to the spec.
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
    </div>
  )
}
