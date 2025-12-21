"use client"

import Link from "next/link"
import { useState } from "react"
import {
  useAllSprints,
  useAllTasks,
  useUpdateTask,
  useCreateTask,
  useProjects,
  useProjectProtocols,
  useCreateSprintFromProtocol,
} from "@/lib/api"
import { SprintBoard } from "@/components/agile/sprint-board"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { LoadingState } from "@/components/ui/loading-state"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Calendar,
  Target,
  TrendingUp,
  Layers,
  FolderKanban,
  BarChart3,
  Kanban,
  Maximize2,
  Minimize2,
  PlayCircle,
  ArrowUpRight,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import type { AgileTask, AgileTaskCreate, AgileTaskUpdate, TaskBoardStatus, Sprint } from "@/lib/api/types"

export default function ExecutionPage() {
  const { data: sprints, isLoading: sprintsLoading } = useAllSprints()
  const { data: tasks, isLoading: tasksLoading, mutate: mutateTasks } = useAllTasks()
  const { data: projects = [] } = useProjects()
  const updateTask = useUpdateTask()
  const createTask = useCreateTask()
  const [filterProject, setFilterProject] = useState<string>("all")
  const [filterSprint, setFilterSprint] = useState<string>("active")
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [createSprintOpen, setCreateSprintOpen] = useState(false)
  const [selectedProtocolId, setSelectedProtocolId] = useState("")
  const [sprintName, setSprintName] = useState("")
  const [sprintStart, setSprintStart] = useState("")
  const [sprintEnd, setSprintEnd] = useState("")

  const selectedProjectId = filterProject !== "all" ? Number.parseInt(filterProject, 10) : null
  const { data: projectProtocols = [] } = useProjectProtocols(selectedProjectId ?? undefined)
  const createSprintFromProtocol = useCreateSprintFromProtocol(selectedProjectId ?? undefined)

  const scopedSprints =
    sprints?.filter((s) => (selectedProjectId ? s.project_id === selectedProjectId : true)) || []
  const scopedTasks =
    tasks?.filter((task) => (selectedProjectId ? task.project_id === selectedProjectId : true)) || []
  const activeSprints = scopedSprints.filter((s) => s.status === "active")
  const planningSprints = scopedSprints.filter((s) => s.status === "planning")
  const completedSprints = scopedSprints.filter((s) => s.status === "completed")

  const filteredTasks =
    scopedTasks.filter((task) => {
      if (filterSprint === "active") {
        return activeSprints.some((s) => s.id === task.sprint_id)
      }
      if (filterSprint === "backlog") {
        return !task.sprint_id
      }
      if (filterSprint !== "all") {
        return task.sprint_id?.toString() === filterSprint
      }
      return true
    }) || []

  const projectIds = projects.map((project) => project.id)
  const projectNameById = new Map(projects.map((project) => [project.id, project.name]))

  const handleTaskUpdate = async (taskId: number, data: { board_status: TaskBoardStatus }) => {
    await updateTask.mutateAsync(taskId, data)
    mutateTasks()
  }

  const handleTaskCreate = async (data: AgileTaskCreate) => {
    if (!selectedProjectId) {
      toast.error("Select a project before creating tasks.")
      return
    }
    await createTask.mutateAsync(selectedProjectId, data)
    mutateTasks()
    toast.success("Task created")
  }

  const handleTaskEdit = async (taskId: number, data: AgileTaskUpdate) => {
    await updateTask.mutateAsync(taskId, data)
    mutateTasks()
    toast.success("Task updated")
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
    const sidebar = document.querySelector("[data-sidebar]")
    const header = document.querySelector("[data-header]")
    const breadcrumbs = document.querySelector("[data-breadcrumbs]")

    if (sidebar) {
      if (!isFullscreen) {
        sidebar.classList.add("w-12")
        sidebar.classList.remove("w-64")
      } else {
        sidebar.classList.remove("w-12")
        sidebar.classList.add("w-64")
      }
    }

    if (header) {
      header.classList.toggle("hidden", !isFullscreen)
    }

    if (breadcrumbs) {
      breadcrumbs.classList.toggle("hidden", !isFullscreen)
    }
  }

  const handleCreateFromProtocol = async () => {
    if (!selectedProjectId) {
      toast.error("Select a project to create an execution sprint.")
      return
    }
    if (!selectedProtocolId) {
      toast.error("Select a protocol run to create an execution sprint.")
      return
    }
    try {
      await createSprintFromProtocol.mutateAsync(Number.parseInt(selectedProtocolId, 10), {
        sprint_name: sprintName || undefined,
        start_date: sprintStart || undefined,
        end_date: sprintEnd || undefined,
      })
      toast.success("Execution sprint created from protocol run.")
      setCreateSprintOpen(false)
      setSelectedProtocolId("")
      setSprintName("")
      setSprintStart("")
      setSprintEnd("")
    } catch {
      toast.error("Failed to create sprint from protocol.")
    }
  }

  if (sprintsLoading || tasksLoading) {
    return <LoadingState message="Loading execution overview..." />
  }

  const totalPoints = filteredTasks.reduce((acc, t) => acc + (t.story_points || 0), 0)
  const completedPoints = filteredTasks
    .filter((t) => t.board_status === "done")
    .reduce((acc, t) => acc + (t.story_points || 0), 0)

  return (
    <div className={cn("min-h-screen bg-background", isFullscreen && "fixed inset-0 z-50 overflow-auto")}>
      <div className="border-b bg-card/50">
        <div className="container py-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Execution Overview</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Cross-project execution status with protocol-driven sprint creation
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={toggleFullscreen} className="gap-2 bg-transparent">
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

          <div className="flex items-center gap-6 py-3 px-4 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-500" />
              <span className="text-sm text-muted-foreground">Active Executions:</span>
              <span className="font-semibold">{activeSprints.length}</span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <FolderKanban className="h-4 w-4 text-purple-500" />
              <span className="text-sm text-muted-foreground">Scoped Tasks:</span>
              <span className="font-semibold">{filteredTasks.length}</span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-green-500" />
              <span className="text-sm text-muted-foreground">Points:</span>
              <span className="font-semibold">
                {completedPoints} / {totalPoints}
              </span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-muted-foreground">Progress:</span>
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
                  setFilterProject(value)
                  if (value === "all") {
                    setSelectedProtocolId("")
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
                <Link href={`/projects/${selectedProjectId}/execution`}>
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
              showBacklog={filterSprint === "backlog" || filterSprint === "all"}
              canCreate={!!selectedProjectId}
            />
          </TabsContent>

          <TabsContent value="sprints">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
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
                    <p className="text-sm text-muted-foreground text-center py-8">No active executions</p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
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
                    <p className="text-sm text-muted-foreground text-center py-8">No executions in planning</p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
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
                    <p className="text-sm text-muted-foreground text-center py-8">No completed executions</p>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="metrics">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Velocity Trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[200px] flex items-end justify-between gap-2">
                    {completedSprints.slice(-5).map((sprint) => (
                      <div key={sprint.id} className="flex-1 flex flex-col items-center gap-2">
                        <div className="w-full flex flex-col items-center">
                          <div
                            className="w-full bg-primary rounded-t"
                            style={{
                              height: `${((sprint.velocity_actual || 0) / 50) * 150}px`,
                              minHeight: "20px",
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">{sprint.velocity_actual || 0}</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground text-center mt-4">Last 5 completed executions velocity</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Task Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {["story", "bug", "task", "spike"].map((type) => {
                      const count = filteredTasks.filter((t) => t.task_type === type).length
                      const percent = filteredTasks.length > 0 ? (count / filteredTasks.length) * 100 : 0
                      return (
                        <div key={type} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="capitalize">{type}s</span>
                            <span className="text-muted-foreground">{count}</span>
                          </div>
                          <Progress value={percent} className="h-2" />
                        </div>
                      )
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
                  <SelectValue placeholder={selectedProjectId ? "Select protocol run" : "Select a project first"} />
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
            <Button onClick={handleCreateFromProtocol} disabled={!selectedProtocolId || selectedProtocolId === "none"}>
              Create Execution
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SprintCard({
  sprint,
  tasks,
  projectName,
}: {
  sprint: Sprint
  tasks: AgileTask[]
  projectName?: string
}) {
  const sprintTasks = tasks.filter((t) => t.sprint_id === sprint.id)
  const totalPoints = sprintTasks.reduce((acc, t) => acc + (t.story_points || 0), 0)
  const completedPoints = sprintTasks
    .filter((t) => t.board_status === "done")
    .reduce((acc, t) => acc + (t.story_points || 0), 0)
  const progress = totalPoints > 0 ? Math.round((completedPoints / totalPoints) * 100) : 0
  const protocolIds = new Set(sprintTasks.map((task) => task.protocol_run_id).filter((id) => id))

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h4 className="font-medium text-sm">{sprint.name}</h4>
            <p className="text-xs text-muted-foreground">
              {projectName ? projectName : `Project #${sprint.project_id}`}
            </p>
          </div>
          <Badge
            variant={sprint.status === "active" ? "default" : sprint.status === "completed" ? "secondary" : "outline"}
            className="text-[10px]"
          >
            {sprint.status}
          </Badge>
        </div>

        {sprint.goal && <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{sprint.goal}</p>}

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progress</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 mt-3 text-xs text-muted-foreground">
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
  )
}
