"use client"

import { useState } from "react"
import { useAllSprints, useAllTasks, useUpdateTask, useCreateTask, useProjects } from "@/lib/api"
import { SprintBoard } from "@/components/agile/sprint-board"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { LoadingState } from "@/components/ui/loading-state"
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
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import type { AgileTask, AgileTaskCreate, AgileTaskUpdate, TaskBoardStatus, Sprint } from "@/lib/api/types"

export default function SprintsPage() {
  const { data: sprints, isLoading: sprintsLoading } = useAllSprints()
  const { data: tasks, isLoading: tasksLoading, mutate: mutateTasks } = useAllTasks()
  const { data: projects } = useProjects()
  const updateTask = useUpdateTask()
  const createTask = useCreateTask()
  const [filterProject, setFilterProject] = useState<string>("all")
  const [filterSprint, setFilterSprint] = useState<string>("active")
  const [isFullscreen, setIsFullscreen] = useState(false)

  const activeSprints = sprints?.filter((s) => s.status === "active") || []
  const planningSprints = sprints?.filter((s) => s.status === "planning") || []
  const completedSprints = sprints?.filter((s) => s.status === "completed") || []

  const filteredTasks =
    tasks?.filter((task) => {
      if (filterProject !== "all" && task.project_id.toString() !== filterProject) return false
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

  const projectIds = [...new Set(tasks?.map((t) => t.project_id) || [])]
  const projectNameById = new Map(projects?.map((project) => [project.id, project.name]) || [])

  const handleTaskUpdate = async (taskId: number, data: { board_status: TaskBoardStatus }) => {
    await updateTask.mutateAsync(taskId, data)
    mutateTasks()
  }

  const handleTaskCreate = async (data: AgileTaskCreate) => {
    const projectId = filterProject !== "all" ? Number.parseInt(filterProject) : 1
    await createTask.mutateAsync(projectId, data)
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

  if (sprintsLoading || tasksLoading) {
    return <LoadingState message="Loading sprints..." />
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
              <h1 className="text-2xl font-bold tracking-tight">Sprint Management</h1>
              <p className="text-sm text-muted-foreground mt-1">Global view of all sprints and tasks across projects</p>
            </div>
            <Button variant="outline" size="sm" onClick={toggleFullscreen} className="gap-2 bg-transparent">
              {isFullscreen ? (
                <>
                  <Minimize2 className="h-4 w-4" />
                  Exit Fullscreen
                </>
              ) : (
                <>
                  <Maximize2 className="h-4 w-4" />
                  Fullscreen Mode
                </>
              )}
            </Button>
          </div>

          <div className="flex items-center gap-6 py-3 px-4 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-500" />
              <span className="text-sm text-muted-foreground">Active Sprints:</span>
              <span className="font-semibold">{activeSprints.length}</span>
            </div>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <FolderKanban className="h-4 w-4 text-purple-500" />
              <span className="text-sm text-muted-foreground">Total Tasks:</span>
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
                Board View
              </TabsTrigger>
              <TabsTrigger value="sprints" className="gap-2">
                <Calendar className="h-4 w-4" />
                Sprint List
              </TabsTrigger>
              <TabsTrigger value="metrics" className="gap-2">
                <BarChart3 className="h-4 w-4" />
                Metrics
              </TabsTrigger>
            </TabsList>

            <div className="flex items-center gap-3">
              <Select value={filterProject} onValueChange={setFilterProject}>
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
                  <SelectValue placeholder="Filter Sprint" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sprints</SelectItem>
                  <SelectItem value="active">Active Sprints</SelectItem>
                  <SelectItem value="backlog">Product Backlog</SelectItem>
                  {sprints?.map((sprint) => (
                    <SelectItem key={sprint.id} value={sprint.id.toString()}>
                      {sprint.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <TabsContent value="board">
            <SprintBoard
              tasks={filteredTasks}
              sprints={sprints || []}
              onTaskUpdate={handleTaskUpdate}
              onTaskCreate={handleTaskCreate}
              onTaskEdit={handleTaskEdit}
              showBacklog={filterSprint === "backlog" || filterSprint === "all"}
            />
          </TabsContent>

          <TabsContent value="sprints">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-green-500" />
                  Active ({activeSprints.length})
                </h3>
                <div className="space-y-3">
                  {activeSprints.map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={tasks || []}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {activeSprints.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">No active sprints</p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-blue-500" />
                  Planning ({planningSprints.length})
                </h3>
                <div className="space-y-3">
                  {planningSprints.map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={tasks || []}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {planningSprints.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">No sprints in planning</p>
                  )}
                </div>
              </div>

              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-slate-500" />
                  Completed ({completedSprints.length})
                </h3>
                <div className="space-y-3">
                  {completedSprints.slice(0, 5).map((sprint) => (
                    <SprintCard
                      key={sprint.id}
                      sprint={sprint}
                      tasks={tasks || []}
                      projectName={projectNameById.get(sprint.project_id)}
                    />
                  ))}
                  {completedSprints.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">No completed sprints</p>
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
                  <p className="text-xs text-muted-foreground text-center mt-4">Last 5 completed sprints velocity</p>
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

        <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {sprint.start_date ? new Date(sprint.start_date).toLocaleDateString() : "Not set"}
          </div>
          <div className="flex items-center gap-1">
            <Target className="h-3 w-3" />
            {completedPoints}/{totalPoints} pts
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
