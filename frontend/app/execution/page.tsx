"use client";

import { useState } from "react";
import Link from "next/link";

import {
  ArrowUpRight,
  BarChart3,
  Calendar,
  FolderKanban,
  Kanban,
  Layers,
  Maximize2,
  Minimize2,
  PlayCircle,
  Target,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

import { SprintBoard } from "@/components/agile/sprint-board";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAllSprints,
  useAllTasks,
  useCreateSprintFromProtocol,
  useCreateTask,
  useExecuteTask,
  useProjectProtocols,
  useProjects,
  useUpdateTask,
} from "@/lib/api";
import type {
  AgileTask,
  AgileTaskCreate,
  AgileTaskUpdate,
  Sprint,
  TaskBoardStatus,
} from "@/lib/api/types";
import { getProjectExecutionPath } from "@/lib/project-routes";
import { cn } from "@/lib/utils";
import { useWebSocketEvent } from "@/lib/websocket/hooks";

export default function ExecutionPage() {
  const { data: sprints, isLoading: sprintsLoading } = useAllSprints();
  const { data: tasks, isLoading: tasksLoading, mutate: mutateTasks } = useAllTasks();
  const { data: projects = [] } = useProjects();
  const updateTask = useUpdateTask();
  const createTask = useCreateTask();
  const executeTask = useExecuteTask();
  const [filterProject, setFilterProject] = useState<string>("all");
  const [filterSprint, setFilterSprint] = useState<string>("active");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [createSprintOpen, setCreateSprintOpen] = useState(false);
  const [selectedProtocolId, setSelectedProtocolId] = useState("");
  const [sprintName, setSprintName] = useState("");
  const [sprintStart, setSprintStart] = useState("");
  const [sprintEnd, setSprintEnd] = useState("");

  // WebSocket real-time updates: invalidate task/sprint queries on changes
  useWebSocketEvent("events", ["task_status_changed", "execution_progress"], (qc) => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
    qc.invalidateQueries({ queryKey: ["sprints"] });
  });

  const selectedProjectId = filterProject !== "all" ? Number.parseInt(filterProject, 10) : null;
  const { data: projectProtocols = [] } = useProjectProtocols(selectedProjectId ?? undefined);
  const createSprintFromProtocol = useCreateSprintFromProtocol(selectedProjectId ?? undefined);

  const scopedSprints =
    sprints?.filter((s) => (selectedProjectId ? s.project_id === selectedProjectId : true)) || [];
  const scopedTasks =
    tasks?.filter((task) => (selectedProjectId ? task.project_id === selectedProjectId : true)) ||
    [];
  const activeSprints = scopedSprints.filter((s) => s.status === "active");
  const planningSprints = scopedSprints.filter((s) => s.status === "planning");
  const completedSprints = scopedSprints.filter((s) => s.status === "completed");

  const filteredTasks =
    scopedTasks.filter((task) => {
      if (filterSprint === "active") {
        return activeSprints.some((s) => s.id === task.sprint_id);
      }
      if (filterSprint === "backlog") {
        return !task.sprint_id;
      }
      if (filterSprint !== "all") {
        return task.sprint_id?.toString() === filterSprint;
      }
      return true;
    }) || [];

  const projectIds = projects.map((project) => project.id);
  const projectNameById = new Map(projects.map((project) => [project.id, project.name]));

  const handleTaskUpdate = async (taskId: number, data: { board_status: TaskBoardStatus }) => {
    await updateTask.mutateAsync(taskId, data);
    mutateTasks();
  };

  const handleTaskCreate = async (data: AgileTaskCreate) => {
    if (!selectedProjectId) {
      toast.error("Select a project before creating tasks.");
      return;
    }
    await createTask.mutateAsync(selectedProjectId, data);
    mutateTasks();
    toast.success("Task created");
  };

  const handleTaskEdit = async (taskId: number, data: AgileTaskUpdate) => {
    await updateTask.mutateAsync(taskId, data);
    mutateTasks();
    toast.success("Task updated");
  };

  const handleTaskExecute = async (taskId: number) => {
    try {
      await executeTask.mutateAsync(taskId);
      mutateTasks();
      toast.success("Task execution started");
    } catch {
      toast.error("Failed to start task execution");
    }
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
    const sidebar = document.querySelector("[data-sidebar]");
    const header = document.querySelector("[data-header]");
    const breadcrumbs = document.querySelector("[data-breadcrumbs]");

    if (sidebar) {
      if (!isFullscreen) {
        sidebar.classList.add("w-12");
        sidebar.classList.remove("w-64");
      } else {
        sidebar.classList.remove("w-12");
        sidebar.classList.add("w-64");
      }
    }

    if (header) {
      header.classList.toggle("hidden", !isFullscreen);
    }

    if (breadcrumbs) {
      breadcrumbs.classList.toggle("hidden", !isFullscreen);
    }
  };

  const handleCreateFromProtocol = async () => {
    if (!selectedProjectId) {
      toast.error("Select a project to create an execution sprint.");
      return;
    }
    if (!selectedProtocolId) {
      toast.error("Select a protocol run to create an execution sprint.");
      return;
    }
    try {
      await createSprintFromProtocol.mutateAsync(Number.parseInt(selectedProtocolId, 10), {
        sprint_name: sprintName || undefined,
        start_date: sprintStart || undefined,
        end_date: sprintEnd || undefined,
      });
      toast.success("Execution sprint created from protocol run.");
      setCreateSprintOpen(false);
      setSelectedProtocolId("");
      setSprintName("");
      setSprintStart("");
      setSprintEnd("");
    } catch {
      toast.error("Failed to create sprint from protocol.");
    }
  };

  if (sprintsLoading || tasksLoading) {
    return <LoadingState message="Loading execution overview..." />;
  }

  const totalPoints = filteredTasks.reduce((acc, t) => acc + (t.story_points || 0), 0);
  const completedPoints = filteredTasks
    .filter((t) => t.board_status === "done")
    .reduce((acc, t) => acc + (t.story_points || 0), 0);

  return (
    <div
      className={cn(
        "bg-background min-h-screen",
        isFullscreen && "fixed inset-0 z-50 overflow-auto"
      )}
    >
      <div className="bg-card/50 border-b">
        <div className="container py-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Execution Overview</h1>
              <p className="text-muted-foreground mt-1 text-sm">
                Cross-project execution status with protocol-driven sprint creation
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleFullscreen}
              className="gap-2 bg-transparent"
            >
              {isFullscreen ? (
                <>
                  <Minimize2 className="h-4 w-4" />
                  Exit Focus Mode
                </>
              ) : (
                <>
                  <Maximize2 className="h-4 w-4" />
                  Focus Mode
                </>
              )}
            </Button>
          </div>

          <div className="bg-muted/50 flex items-center gap-6 rounded-lg px-4 py-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-500" />
              <span className="text-muted-foreground text-sm">Active Executions:</span>
              <span className="font-semibold">{activeSprints.length}</span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <FolderKanban className="h-4 w-4 text-purple-500" />
              <span className="text-muted-foreground text-sm">Scoped Tasks:</span>
              <span className="font-semibold">{filteredTasks.length}</span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-green-500" />
              <span className="text-muted-foreground text-sm">Points:</span>
              <span className="font-semibold">
                {completedPoints} / {totalPoints}
              </span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-amber-500" />
              <span className="text-muted-foreground text-sm">Progress:</span>
              <span className="font-semibold">
                {totalPoints > 0 ? Math.round((completedPoints / totalPoints) * 100) : 0}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-6">
        <Tabs defaultValue="board" className="space-y-6">
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="board" className="gap-2">
                <Kanban className="h-4 w-4" />
                Execution Board
              </TabsTrigger>
              <TabsTrigger value="sprints" className="gap-2">
                <Calendar className="h-4 w-4" />
                Execution List
              </TabsTrigger>
              <TabsTrigger value="metrics" className="gap-2">
                <BarChart3 className="h-4 w-4" />
                Metrics
              </TabsTrigger>
            </TabsList>

            <div className="flex items-center gap-3">
              <Select
                value={filterProject}
                onValueChange={(value) => {
                  setFilterProject(value);
                  if (value === "all") {
                    setSelectedProtocolId("");
                  }
                }}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All Projects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Projects</SelectItem>
                  {projectIds.map((id) => (
                    <SelectItem key={id} value={id.toString()}>
                      {projectNameById.get(id) || `Project #${id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={filterSprint} onValueChange={setFilterSprint}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter Execution" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Executions</SelectItem>
                  <SelectItem value="active">Active Executions</SelectItem>
                  <SelectItem value="backlog">Execution Backlog</SelectItem>
                  {scopedSprints.map((sprint) => (
                    <SelectItem key={sprint.id} value={sprint.id.toString()}>
                      {sprint.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                size="sm"
                className="gap-2"
                onClick={() => setCreateSprintOpen(true)}
                disabled={!selectedProjectId}
              >
                <PlayCircle className="h-4 w-4" />
                Create from Protocol
              </Button>

              {selectedProjectId && (
                <Link href={getProjectExecutionPath(selectedProjectId)}>
                  <Button size="sm" variant="outline" className="gap-2">
                    <ArrowUpRight className="h-4 w-4" />
                    Open Project Execution
                  </Button>
                </Link>
              )}
            </div>
          </div>

          <TabsContent value="board">
            <SprintBoard
              tasks={filteredTasks}
              sprints={scopedSprints}
              onTaskUpdate={handleTaskUpdate}
              onTaskCreate={handleTaskCreate}
              onTaskEdit={handleTaskEdit}
              onTaskExecute={handleTaskExecute}
              showBacklog={filterSprint === "backlog" || filterSprint === "all"}
              canCreate={!!selectedProjectId}
            />
          </TabsContent>

          <TabsContent value="sprints">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <div>
                <h3 className="mb-3 flex items-center gap-2 font-semibold">
                  <div className="h-2 w-2 rounded-full bg-green-500" />
                  Active Executions ({activeSprints.length})
                </h3>
                <div className="space-y-3">
                  {activeSprints.map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={scopedTasks}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {activeSprints.length === 0 && (
                    <p className="text-muted-foreground py-8 text-center text-sm">
                      No active executions
                    </p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="mb-3 flex items-center gap-2 font-semibold">
                  <div className="h-2 w-2 rounded-full bg-blue-500" />
                  Planning Executions ({planningSprints.length})
                </h3>
                <div className="space-y-3">
                  {planningSprints.map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={scopedTasks}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {planningSprints.length === 0 && (
                    <p className="text-muted-foreground py-8 text-center text-sm">
                      No executions in planning
                    </p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="mb-3 flex items-center gap-2 font-semibold">
                  <div className="h-2 w-2 rounded-full bg-slate-500" />
                  Completed Executions ({completedSprints.length})
                </h3>
                <div className="space-y-3">
                  {completedSprints.slice(0, 5).map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={scopedTasks}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {completedSprints.length === 0 && (
                    <p className="text-muted-foreground py-8 text-center text-sm">
                      No completed executions
                    </p>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="metrics">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Velocity Trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex h-[200px] items-end justify-between gap-2">
                    {completedSprints.slice(-5).map((sprint) => (
                      <div key={sprint.id} className="flex flex-1 flex-col items-center gap-2">
                        <div className="flex w-full flex-col items-center">
                          <div
                            className="bg-primary w-full rounded-t"
                            style={{
                              height: `${((sprint.velocity_actual || 0) / 50) * 150}px`,
                              minHeight: "20px",
                            }}
                          />
                        </div>
                        <span className="text-muted-foreground text-xs">
                          {sprint.velocity_actual || 0}
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-muted-foreground mt-4 text-center text-xs">
                    Last 5 completed executions velocity
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Task Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {["story", "bug", "task", "spike"].map((type) => {
                      const count = filteredTasks.filter((t) => t.task_type === type).length;
                      const percent =
                        filteredTasks.length > 0 ? (count / filteredTasks.length) * 100 : 0;
                      return (
                        <div key={type} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="capitalize">{type}s</span>
                            <span className="text-muted-foreground">{count}</span>
                          </div>
                          <Progress value={percent} className="h-2" />
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={createSprintOpen} onOpenChange={setCreateSprintOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Execution from Protocol</DialogTitle>
            <DialogDescription>
              Select a protocol run to generate a new execution sprint and sync tasks.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Protocol Run</Label>
              <Select value={selectedProtocolId} onValueChange={setSelectedProtocolId}>
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      selectedProjectId ? "Select protocol run" : "Select a project first"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {projectProtocols.length === 0 && (
                    <SelectItem value="none" disabled>
                      No protocol runs found
                    </SelectItem>
                  )}
                  {projectProtocols.map((protocol) => (
                    <SelectItem key={protocol.id} value={protocol.id.toString()}>
                      {protocol.protocol_name} #{protocol.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="sprint-name">Execution Name (optional)</Label>
              <Input
                id="sprint-name"
                value={sprintName}
                onChange={(event) => setSprintName(event.target.value)}
                placeholder="Protocol-based execution"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sprint-start">Start Date</Label>
                <Input
                  id="sprint-start"
                  type="date"
                  value={sprintStart}
                  onChange={(event) => setSprintStart(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sprint-end">End Date</Label>
                <Input
                  id="sprint-end"
                  type="date"
                  value={sprintEnd}
                  onChange={(event) => setSprintEnd(event.target.value)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateSprintOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateFromProtocol}
              disabled={!selectedProtocolId || selectedProtocolId === "none"}
            >
              Create Execution
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SprintCard({
  sprint,
  tasks,
  projectName,
}: {
  sprint: Sprint;
  tasks: AgileTask[];
  projectName?: string;
}) {
  const sprintTasks = tasks.filter((t) => t.sprint_id === sprint.id);
  const totalPoints = sprintTasks.reduce((acc, t) => acc + (t.story_points || 0), 0);
  const completedPoints = sprintTasks
    .filter((t) => t.board_status === "done")
    .reduce((acc, t) => acc + (t.story_points || 0), 0);
  const progress = totalPoints > 0 ? Math.round((completedPoints / totalPoints) * 100) : 0;
  const protocolIds = new Set(sprintTasks.map((task) => task.protocol_run_id).filter((id) => id));

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="p-4">
        <div className="mb-2 flex items-start justify-between">
          <div>
            <h4 className="text-sm font-medium">{sprint.name}</h4>
            <p className="text-muted-foreground text-xs">
              {projectName ? projectName : `Project #${sprint.project_id}`}
            </p>
          </div>
          <Badge
            variant={
              sprint.status === "active"
                ? "default"
                : sprint.status === "completed"
                  ? "secondary"
                  : "outline"
            }
            className="text-[10px]"
          >
            {sprint.status}
          </Badge>
        </div>

        {sprint.goal && (
          <p className="text-muted-foreground mb-3 line-clamp-2 text-xs">{sprint.goal}</p>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progress</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>

        <div className="text-muted-foreground mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {sprint.start_date ? new Date(sprint.start_date).toLocaleDateString() : "Not set"}
          </div>
          <div className="flex items-center gap-1">
            <Target className="h-3 w-3" />
            {completedPoints}/{totalPoints} pts
          </div>
          {protocolIds.size > 0 && (
            <div className="flex items-center gap-1">
              <PlayCircle className="h-3 w-3" />
              {protocolIds.size} protocol{protocolIds.size === 1 ? "" : "s"}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
