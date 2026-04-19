"use client";

import { useMemo,useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { format } from "date-fns";
import {
  Calendar as CalendarIcon,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  FileSearch,
  FileText,
  Filter,
  FolderKanban,
  Layers,
  ListTodo,
  MessageSquare,
  PlayCircle,
  Plus,
  Search,
  Target,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type Specification,
  type SpecificationFilters,
  useAnalyzeSpec,
  useClarifySpec,
  useCleanupSpecRun,
  useCreateProtocolFromSpec,
  useGenerateChecklist,
  useProjects,
  useRunImplement,
  useSpecificationsWithMeta,
} from "@/lib/api";
import { getSpecificationDetailPath, getSpecificationReviewPath } from "@/lib/project-routes";
import { getImplementSuccessOutcome } from "@/lib/workflow/implement-result";

export default function SpecificationsPage() {
  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [workflowFilter, setWorkflowFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState<Date | undefined>();
  const [dateTo, setDateTo] = useState<Date | undefined>();
  const [showFilters, setShowFilters] = useState(false);

  // Build filters for API
  const filters: SpecificationFilters = useMemo(() => {
    const f: SpecificationFilters = {};
    if (projectFilter !== "all") f.project_id = parseInt(projectFilter);
    if (statusFilter !== "all") f.status = statusFilter as "draft" | "in-progress" | "completed";
    if (workflowFilter === "has_plan") f.has_plan = true;
    if (workflowFilter === "has_tasks") f.has_tasks = true;
    if (workflowFilter === "spec_only") {
      f.has_plan = false;
      f.has_tasks = false;
    }
    if (dateFrom) f.date_from = dateFrom.toISOString().split("T")[0];
    if (dateTo) f.date_to = dateTo.toISOString().split("T")[0];
    if (searchQuery) f.search = searchQuery;
    return f;
  }, [projectFilter, statusFilter, workflowFilter, dateFrom, dateTo, searchQuery]);

  // Fetch data
  const { data: specsData, isLoading } = useSpecificationsWithMeta(filters);
  const { data: projects } = useProjects();
  const clarifySpec = useClarifySpec();
  const generateChecklist = useGenerateChecklist();
  const analyzeSpec = useAnalyzeSpec();
  const runImplement = useRunImplement();
  const createProtocolFromSpec = useCreateProtocolFromSpec();
  const cleanupSpecRun = useCleanupSpecRun();
  const router = useRouter();

  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyTarget, setClarifyTarget] = useState<{
    projectId: number;
    specPath: string;
    specRunId?: number;
  } | null>(null);
  const [clarifyQuestion, setClarifyQuestion] = useState("");
  const [clarifyAnswer, setClarifyAnswer] = useState("");
  const [clarifyNotes, setClarifyNotes] = useState("");
  const [cleanupOpen, setCleanupOpen] = useState(false);
  const [cleanupDeleteRemote, setCleanupDeleteRemote] = useState(false);
  const [cleanupTarget, setCleanupTarget] = useState<Specification | null>(null);

  const specifications = specsData?.items || [];
  const total = specsData?.total || 0;

  const activeFiltersCount = [
    projectFilter !== "all",
    statusFilter !== "all",
    workflowFilter !== "all",
    dateFrom,
    dateTo,
  ].filter(Boolean).length;

  const clearFilters = () => {
    setProjectFilter("all");
    setStatusFilter("all");
    setWorkflowFilter("all");
    setDateFrom(undefined);
    setDateTo(undefined);
    setSearchQuery("");
  };

  const statusColors: Record<string, string> = {
    draft: "bg-slate-500",
    "in-progress": "bg-blue-500",
    completed: "bg-green-500",
    cleaned: "bg-zinc-500",
    failed: "bg-red-700",
  };

  const statusLabels: Record<string, string> = {
    draft: "Draft",
    "in-progress": "In Progress",
    completed: "Completed",
    cleaned: "Cleaned",
    failed: "Failed",
  };

  const openClarify = (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available");
      return;
    }
    setClarifyTarget({
      projectId: spec.project_id,
      specPath: spec.spec_path,
      specRunId: spec.spec_run_id ?? undefined,
    });
    setClarifyOpen(true);
  };

  const handleClarify = async () => {
    if (!clarifyTarget) {
      toast.error("Select a spec to clarify");
      return;
    }

    const hasEntry = clarifyQuestion.trim() && clarifyAnswer.trim();
    const hasNotes = clarifyNotes.trim();

    if (!hasEntry && !hasNotes) {
      toast.error("Provide a question/answer or notes");
      return;
    }

    try {
      const result = await clarifySpec.mutateAsync({
        project_id: clarifyTarget.projectId,
        spec_path: clarifyTarget.specPath,
        entries: hasEntry
          ? [{ question: clarifyQuestion.trim(), answer: clarifyAnswer.trim() }]
          : [],
        notes: hasNotes ? clarifyNotes.trim() : undefined,
        spec_run_id: clarifyTarget.specRunId,
      });
      if (result.success) {
        toast.success(`Clarifications added (${result.clarifications_added})`);
        setClarifyOpen(false);
        setClarifyQuestion("");
        setClarifyAnswer("");
        setClarifyNotes("");
      } else {
        toast.error(result.error || "Clarification failed");
      }
    } catch {
      toast.error("Clarification failed");
    }
  };

  const handleChecklist = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available");
      return;
    }
    try {
      const result = await generateChecklist.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
        spec_run_id: spec.spec_run_id ?? undefined,
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

  const handleAnalyze = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available");
      return;
    }
    try {
      const result = await analyzeSpec.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
        plan_path: spec.plan_path || undefined,
        tasks_path: spec.tasks_path || undefined,
        spec_run_id: spec.spec_run_id ?? undefined,
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

  const handleImplement = async (spec: Specification) => {
    if (!spec.spec_path) {
      toast.error("Spec file path not available");
      return;
    }
    try {
      const result = await runImplement.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path,
        spec_run_id: spec.spec_run_id ?? undefined,
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

  const handleCreateProtocol = async (spec: Specification) => {
    if (!spec.tasks_path) {
      toast.error("Tasks path not available yet");
      return;
    }
    try {
      const result = await createProtocolFromSpec.mutateAsync({
        project_id: spec.project_id,
        spec_path: spec.spec_path || undefined,
        tasks_path: spec.tasks_path,
        protocol_name: spec.path?.split("/").pop() || undefined,
        spec_run_id: spec.spec_run_id ?? undefined,
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

  const openCleanup = (spec: Specification) => {
    if (!spec.spec_run_id) {
      toast.error("SpecRun id not available");
      return;
    }
    setCleanupTarget(spec);
    setCleanupDeleteRemote(false);
    setCleanupOpen(true);
  };

  const getSpecificationEntry = (spec: Specification) => {
    const hasReviewSurface = Boolean(
      spec.has_tasks ||
        spec.checklist_path ||
        spec.analysis_path ||
        spec.implement_path ||
        spec.protocol_id
    );

    return hasReviewSurface
      ? { href: getSpecificationReviewPath(spec.id), label: "Review" }
      : { href: getSpecificationDetailPath(spec.id), label: "View" };
  };

  const handleCleanup = async () => {
    if (!cleanupTarget?.spec_run_id) {
      toast.error("SpecRun id not available");
      return;
    }
    try {
      const result = await cleanupSpecRun.mutateAsync({
        specRunId: cleanupTarget.spec_run_id,
        payload: { delete_remote_branch: cleanupDeleteRemote },
      });
      if (result.success) {
        toast.success("Spec run cleaned up");
        setCleanupOpen(false);
      } else {
        toast.error(result.error || "Cleanup failed");
      }
    } catch {
      toast.error("Cleanup failed");
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading specifications..." />;
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Specifications</h1>
          <p className="text-muted-foreground text-sm">
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
      <div className="bg-card flex items-center gap-4 rounded-lg border px-4 py-3 text-sm">
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
            <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
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
                      <Button
                        variant="outline"
                        className="w-full justify-start text-left font-normal"
                      >
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
                      <Button
                        variant="outline"
                        className="w-full justify-start text-left font-normal"
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateTo ? format(dateTo, "PP") : "Pick a date"}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar mode="single" selected={dateTo} onSelect={setDateTo} initialFocus />
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
        {specifications.map((spec) => {
          const isCleaned = spec.status === "cleaned";
          const entryAction = getSpecificationEntry(spec);
          return (
            <Card key={spec.id} className="hover:bg-muted/50 transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <FileText className="mt-0.5 h-5 w-5 text-blue-500" />
                    <div>
                      <CardTitle className="text-base">{spec.title}</CardTitle>
                      <CardDescription className="mt-1 font-mono text-xs">
                        <span className="block">{spec.path}</span>
                        {spec.branch_name && (
                          <span className="text-muted-foreground block">
                            branch: {spec.branch_name}
                          </span>
                        )}
                        {spec.worktree_path && (
                          <span className="text-muted-foreground block truncate">
                            worktree: {spec.worktree_path}
                          </span>
                        )}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Workflow Status Badges */}
                    <div className="flex items-center gap-1">
                      <Badge
                        variant={
                          spec.has_tasks ? "default" : spec.has_plan ? "secondary" : "outline"
                        }
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
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-muted-foreground flex items-center gap-4 text-xs">
                    <Link
                      href={`/projects/${spec.project_id}`}
                      className="hover:text-foreground flex items-center gap-1 transition-colors"
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
                      <Link href={entryAction.href}>{entryAction.label}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/projects/${spec.project_id}?tab=spec`}>Project</Link>
                    </Button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openClarify(spec)}
                    disabled={!spec.spec_path || isCleaned}
                  >
                    <MessageSquare className="mr-2 h-4 w-4" />
                    Clarify
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleChecklist(spec)}
                    disabled={!spec.spec_path || isCleaned}
                  >
                    <ClipboardCheck className="mr-2 h-4 w-4" />
                    Checklist
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAnalyze(spec)}
                    disabled={!spec.spec_path || isCleaned}
                  >
                    <FileSearch className="mr-2 h-4 w-4" />
                    Analyze
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCreateProtocol(spec)}
                    disabled={!spec.tasks_path || isCleaned}
                  >
                    <ClipboardList className="mr-2 h-4 w-4" />
                    Create Protocol
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleImplement(spec)}
                    disabled={!spec.spec_path || isCleaned}
                  >
                    <PlayCircle className="mr-2 h-4 w-4" />
                    Implement
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openCleanup(spec)}
                    disabled={!spec.spec_run_id || isCleaned}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Cleanup
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
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

      <Dialog open={cleanupOpen} onOpenChange={setCleanupOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cleanup Spec Run</DialogTitle>
            <DialogDescription>
              Remove the worktree and spec artifacts. Optionally delete the remote branch.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <div className="space-y-1">
                <p className="text-sm font-medium">Delete remote branch</p>
                <p className="text-muted-foreground text-xs">Requires explicit opt-in.</p>
              </div>
              <Switch
                checked={cleanupDeleteRemote}
                onCheckedChange={(value) => setCleanupDeleteRemote(Boolean(value))}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCleanupOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCleanup} disabled={cleanupSpecRun.isPending}>
                {cleanupSpecRun.isPending ? "Cleaning..." : "Confirm Cleanup"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
