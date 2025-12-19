"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import {
  useSpecificationsWithMeta,
  useProjects,
  useClarifySpec,
  useGenerateChecklist,
  useAnalyzeSpec,
  useRunImplement,
  useCreateProtocolFromSpec,
  type SpecificationFilters,
  type Specification,
} from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import { Separator } from "@/components/ui/separator"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  FileText,
  Search,
  Plus,
  Filter,
  ListTodo,
  Target,
  Calendar as CalendarIcon,
  X,
  FolderKanban,
  CheckCircle2,
  ClipboardList,
  Layers,
  MessageSquare,
  ClipboardCheck,
  FileSearch,
  PlayCircle,
} from "lucide-react"
import Link from "next/link"
import { format } from "date-fns"
import { toast } from "sonner"

export default function SpecificationsPage() {
  // Filter state
  const [searchQuery, setSearchQuery] = useState("")
  const [projectFilter, setProjectFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [workflowFilter, setWorkflowFilter] = useState<string>("all")
  const [dateFrom, setDateFrom] = useState<Date | undefined>()
  const [dateTo, setDateTo] = useState<Date | undefined>()
  const [showFilters, setShowFilters] = useState(false)

  // Build filters for API
  const filters: SpecificationFilters = useMemo(() => {
    const f: SpecificationFilters = {}
    if (projectFilter !== "all") f.project_id = parseInt(projectFilter)
    if (statusFilter !== "all") f.status = statusFilter as "draft" | "in-progress" | "completed"
    if (workflowFilter === "has_plan") f.has_plan = true
    if (workflowFilter === "has_tasks") f.has_tasks = true
    if (workflowFilter === "spec_only") {
      f.has_plan = false
      f.has_tasks = false
    }
    if (dateFrom) f.date_from = dateFrom.toISOString().split("T")[0]
    if (dateTo) f.date_to = dateTo.toISOString().split("T")[0]
    if (searchQuery) f.search = searchQuery
    return f
  }, [projectFilter, statusFilter, workflowFilter, dateFrom, dateTo, searchQuery])

  // Fetch data
  const { data: specsData, isLoading } = useSpecificationsWithMeta(filters)
  const { data: projects } = useProjects()
  const clarifySpec = useClarifySpec()
  const generateChecklist = useGenerateChecklist()
  const analyzeSpec = useAnalyzeSpec()
  const runImplement = useRunImplement()
  const createProtocolFromSpec = useCreateProtocolFromSpec()
  const router = useRouter()

  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifyTarget, setClarifyTarget] = useState<{ projectId: number; specPath: string } | null>(null)
  const [clarifyQuestion, setClarifyQuestion] = useState("")
  const [clarifyAnswer, setClarifyAnswer] = useState("")
  const [clarifyNotes, setClarifyNotes] = useState("")

  const specifications = specsData?.items || []
  const total = specsData?.total || 0

  const activeFiltersCount = [
    projectFilter !== "all",
    statusFilter !== "all",
    workflowFilter !== "all",
    dateFrom,
    dateTo,
  ].filter(Boolean).length

  const clearFilters = () => {
    setProjectFilter("all")
    setStatusFilter("all")
    setWorkflowFilter("all")
    setDateFrom(undefined)
    setDateTo(undefined)
    setSearchQuery("")
  }

  const statusColors: Record<string, string> = {
    draft: "bg-slate-500",
    "in-progress": "bg-blue-500",
    completed: "bg-green-500",
  }

  const statusLabels: Record<string, string> = {
    draft: "Draft",
    "in-progress": "In Progress",
    completed: "Completed",
  }

  const openClarify = (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available")
      return
    }
    setClarifyTarget({ projectId: spec.project_id, specPath: spec.spec_path })
    setClarifyOpen(true)
  }

  const handleClarify = async () => {
    if (!clarifyTarget) {
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
        project_id: clarifyTarget.projectId,
        spec_path: clarifyTarget.specPath,
        entries: hasEntry ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }] : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
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

  const handleChecklist = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available")
      return
    }
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
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

  const handleAnalyze = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available")
      return
    }
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
        plan_path: spec.plan_path || undefined,
        tasks_path: spec.tasks_path || undefined,
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

  const handleImplement = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available")
      return
    }
    try {
      const result = await runImplement.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
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

  const handleCreateProtocol = async (spec: Specification) => {
    if (!spec.tasks_path) {
      toast.error("Tasks path not available yet")
      return
    }
    try {
      const result = await createProtocolFromSpec.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path || undefined,
        tasks_path: spec.tasks_path,
        protocol_name: spec.path?.split("/").pop() || undefined,
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

  if (isLoading) {
    return <LoadingState message="Loading specifications..." />
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Specifications</h1>
          <p className="text-sm text-muted-foreground">
            Feature specifications and implementation plans across all projects
          </p>
        </div>
        <Button asChild>
          <Link href="/projects">
            <Plus className="mr-2 h-4 w-4" />
            New Spec
          </Link>
        </Button>
      </div>

      {/* Stats Bar */}
      <div className="flex items-center gap-4 rounded-lg border bg-card px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-blue-500" />
          <span className="font-medium">Total:</span>
          <span className="text-muted-foreground">{total}</span>
        </div>
        <Separator orientation="vertical" className="h-4" />
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-amber-500" />
          <span className="font-medium">With Plan:</span>
          <span className="text-muted-foreground">
            {specifications.filter((s) => s.has_plan).length}
          </span>
        </div>
        <Separator orientation="vertical" className="h-4" />
        <div className="flex items-center gap-2">
          <ListTodo className="h-4 w-4 text-green-500" />
          <span className="font-medium">With Tasks:</span>
          <span className="text-muted-foreground">
            {specifications.filter((s) => s.has_tasks).length}
          </span>
        </div>
        {activeFiltersCount > 0 && (
          <>
            <Separator orientation="vertical" className="h-4" />
            <Badge variant="secondary" className="gap-1">
              <Filter className="h-3 w-3" />
              {activeFiltersCount} filter{activeFiltersCount > 1 ? "s" : ""} active
            </Badge>
          </>
        )}
      </div>

      {/* Search and Filters */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by title, path, or project name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Project Filter */}
          <Select value={projectFilter} onValueChange={setProjectFilter}>
            <SelectTrigger className="w-[200px]">
              <FolderKanban className="mr-2 h-4 w-4" />
              <SelectValue placeholder="All Projects" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Projects</SelectItem>
              <Separator className="my-1" />
              {projects?.map((project) => (
                <SelectItem key={project.id} value={project.id.toString()}>
                  {project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Status Filter */}
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <Separator className="my-1" />
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="in-progress">In Progress</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant={showFilters ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-2 h-4 w-4" />
            More Filters
            {activeFiltersCount > 0 && (
              <Badge variant="default" className="ml-2 h-5 px-1.5">
                {activeFiltersCount}
              </Badge>
            )}
          </Button>

          {activeFiltersCount > 0 && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X className="mr-2 h-4 w-4" />
              Clear
            </Button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <Card>
            <CardContent className="pt-4">
              <div className="grid gap-4 md:grid-cols-4">
                {/* Workflow Stage */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Workflow Stage</label>
                  <Select value={workflowFilter} onValueChange={setWorkflowFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Stages" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Stages</SelectItem>
                      <Separator className="my-1" />
                      <SelectItem value="spec_only">Spec Only</SelectItem>
                      <SelectItem value="has_plan">Has Plan</SelectItem>
                      <SelectItem value="has_tasks">Has Tasks</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Date From */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Created From</label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateFrom ? format(dateFrom, "PP") : "Pick a date"}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={dateFrom}
                        onSelect={setDateFrom}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>

                {/* Date To */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Created To</label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateTo ? format(dateTo, "PP") : "Pick a date"}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={dateTo}
                        onSelect={setDateTo}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Empty State */}
      {specifications.length === 0 && (
        <EmptyState
          icon={FileText}
          title={activeFiltersCount > 0 ? "No matching specifications" : "No specifications found"}
          description={
            activeFiltersCount > 0
              ? "Try adjusting your filters to find specifications."
              : "Create specifications using SpecKit to see them here."
          }
          action={
            activeFiltersCount > 0 ? (
              <Button variant="outline" onClick={clearFilters}>
                Clear Filters
              </Button>
            ) : (
              <Button asChild>
                <Link href="/projects">
                  <Plus className="mr-2 h-4 w-4" />
                  Go to Projects
                </Link>
              </Button>
            )
          }
        />
      )}

      {/* Specifications List */}
      <div className="grid gap-4">
        {specifications.map((spec) => (
          <Card key={spec.id} className="transition-colors hover:bg-muted/50">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <FileText className="mt-0.5 h-5 w-5 text-blue-500" />
                  <div>
                    <CardTitle className="text-base">{spec.title}</CardTitle>
                    <CardDescription className="mt-1 font-mono text-xs">
                      {spec.path}
                    </CardDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Workflow Status Badges */}
                  <div className="flex items-center gap-1">
                    <Badge
                      variant={spec.has_tasks ? "default" : spec.has_plan ? "secondary" : "outline"}
                      className="text-xs"
                    >
                      {spec.has_tasks ? (
                        <>
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Tasks
                        </>
                      ) : spec.has_plan ? (
                        <>
                          <ClipboardList className="mr-1 h-3 w-3" />
                          Plan
                        </>
                      ) : (
                        <>
                          <Layers className="mr-1 h-3 w-3" />
                          Spec
                        </>
                      )}
                    </Badge>
                  </div>
                  <Badge
                    variant="secondary"
                    className={`${statusColors[spec.status] || "bg-slate-500"} text-white`}
                  >
                    {statusLabels[spec.status] || spec.status}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <Link
                    href={`/projects/${spec.project_id}`}
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    <FolderKanban className="h-3 w-3" />
                    {spec.project_name}
                  </Link>
                  {spec.created_at && (
                    <>
                      <span>•</span>
                      <span>{spec.created_at.split("T")[0]}</span>
                    </>
                  )}
                  {spec.sprint_name && (
                    <>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <Target className="h-3 w-3 text-purple-500" />
                        <span className="text-purple-500">{spec.sprint_name}</span>
                      </div>
                    </>
                  )}
                  {spec.story_points > 0 && (
                    <>
                      <span>•</span>
                      <span className="font-medium">{spec.story_points} pts</span>
                    </>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/specifications/${spec.id}`}>View</Link>
                  </Button>
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/projects/${spec.project_id}?tab=spec`}>Project</Link>
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => openClarify(spec)} disabled={!spec.spec_path}>
                  <MessageSquare className="mr-2 h-4 w-4" />
                  Clarify
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleChecklist(spec)} disabled={!spec.spec_path}>
                  <ClipboardCheck className="mr-2 h-4 w-4" />
                  Checklist
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleAnalyze(spec)} disabled={!spec.spec_path}>
                  <FileSearch className="mr-2 h-4 w-4" />
                  Analyze
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCreateProtocol(spec)}
                  disabled={!spec.tasks_path}
                >
                  <ClipboardList className="mr-2 h-4 w-4" />
                  Create Protocol
                </Button>
                <Button size="sm" onClick={() => handleImplement(spec)} disabled={!spec.spec_path}>
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Implement
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
        <DialogContent className="max-w-xl">
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
    </div>
  )
}
