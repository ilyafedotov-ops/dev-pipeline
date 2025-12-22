"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import {
  useSprints,
  useTasks,
  useSprintMetrics,
  useUpdateTask,
  useCreateTask,
  useProjectProtocols,
  useCreateSprintFromProtocol,
} from "@/lib/api"
import { SprintBoard } from "@/components/agile/sprint-board"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { LoadingState } from "@/components/ui/loading-state"
import { BurndownChart } from "@/components/visualizations/burndown-chart"
import { VelocityTrendChart } from "@/components/visualizations/velocity-trend-chart"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Calendar,
  Target,
  TrendingUp,
  CheckCircle2,
  Plus,
  BarChart3,
  ListTodo,
  Maximize2,
  ExternalLink,
} from "lucide-react"
import { toast } from "sonner"
import type { AgileTaskCreate, AgileTaskUpdate, TaskBoardStatus } from "@/lib/api/types"

interface SprintTabProps {
  projectId: number
}

export function SprintTab({ projectId }: SprintTabProps) {
  const { data: sprints, isLoading: sprintsLoading } = useSprints(projectId)
  const [selectedExecution, setSelectedExecution] = useState<string | null>(null)
  const activeSprint = sprints?.find((s) => s.status === "active")
  const resolvedExecution = selectedExecution || (activeSprint ? activeSprint.id.toString() : null)
  const selectedSprintId =
    resolvedExecution && resolvedExecution !== "all" && resolvedExecution !== "backlog"
      ? Number.parseInt(resolvedExecution, 10)
      : null
  const { data: tasks, isLoading: tasksLoading, mutate: mutateTasks } = useTasks(projectId)
  const { data: metrics } = useSprintMetrics(selectedSprintId)
  const updateTask = useUpdateTask()
  const createTask = useCreateTask()
  const { data: projectProtocols = [] } = useProjectProtocols(projectId)
  const createSprintFromProtocol = useCreateSprintFromProtocol(projectId)
  const [createSprintOpen, setCreateSprintOpen] = useState(false)
  const [selectedProtocolId, setSelectedProtocolId] = useState("")
  const [sprintName, setSprintName] = useState("")
  const [sprintStart, setSprintStart] = useState("")
  const [sprintEnd, setSprintEnd] = useState("")

  const currentSprint =
    selectedSprintId != null
      ? sprints?.find((s) => s.id === selectedSprintId)
      : resolvedExecution
        ? undefined
        : activeSprint

  const handleTaskUpdate = async (taskId: number, data: { board_status: TaskBoardStatus }) => {
    await updateTask.mutateAsync(taskId, data)
    mutateTasks()
  }

  const handleTaskCreate = async (data: AgileTaskCreate) => {
    const sprintId =
      resolvedExecution === "backlog" ? undefined : selectedSprintId ?? data.sprint_id
    await createTask.mutateAsync(projectId, { ...data, sprint_id: sprintId })
    mutateTasks()
    toast.success("Task created")
  }

  const handleTaskEdit = async (taskId: number, data: AgileTaskUpdate) => {
    await updateTask.mutateAsync(taskId, data)
    mutateTasks()
    toast.success("Task updated")
  }

  const handleCreateSprint = async () => {
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
      toast.success("Execution sprint created")
      setCreateSprintOpen(false)
      setSelectedProtocolId("")
      setSprintName("")
      setSprintStart("")
      setSprintEnd("")
    } catch {
      toast.error("Failed to create execution sprint")
    }
  }

  const scopedTasks = useMemo(() => {
    const allTasks = tasks || []
    if (resolvedExecution === "backlog") {
      return allTasks.filter((task) => !task.sprint_id)
    }
    if (!resolvedExecution || resolvedExecution === "all") {
      return allTasks
    }
    return allTasks.filter((task) => task.sprint_id === selectedSprintId)
  }, [tasks, resolvedExecution, selectedSprintId])
  const completionPercent = metrics ? Math.round((metrics.completed_points / metrics.total_points) * 100) || 0 : 0

  if (sprintsLoading) {
    return <LoadingState message="Loading execution..." />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Select value={resolvedExecution || ""} onValueChange={setSelectedExecution}>
            <SelectTrigger className="w-[240px] h-9">
              <SelectValue placeholder="Select execution" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Executions</SelectItem>
              <SelectItem value="backlog">Execution Backlog</SelectItem>
              {sprints?.map((sprint) => (
                <SelectItem key={sprint.id} value={sprint.id.toString()}>
                  <div className="flex items-center gap-2">
                    {sprint.name}
                    <Badge variant={sprint.status === "active" ? "default" : "secondary"} className="text-[10px] h-4">
                      {sprint.status}
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {currentSprint && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {currentSprint.start_date} - {currentSprint.end_date}
              </div>
              <Separator orientation="vertical" className="h-4" />
              <div className="flex items-center gap-1">
                <Target className="h-3 w-3" />
                {currentSprint.velocity_planned} pts
              </div>
              <Separator orientation="vertical" className="h-4" />
              <div className="flex items-center gap-1">
                <TrendingUp className="h-3 w-3 text-green-500" />
                {completionPercent}%
              </div>
              <Separator orientation="vertical" className="h-4" />
              <div className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                {metrics?.completed_tasks || 0}/{metrics?.total_tasks || 0}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setCreateSprintOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Create from Protocol
          </Button>
          <Button size="sm" variant="default" asChild>
            <Link href={`/projects/${projectId}/execution`}>
              <Maximize2 className="h-4 w-4 mr-1" />
              Full Execution
              <ExternalLink className="h-3 w-3 ml-1" />
            </Link>
          </Button>
        </div>
      </div>

      {currentSprint?.goal && (
        <div className="p-2 bg-muted/50 rounded border flex items-center gap-2 text-sm">
          <Target className="h-4 w-4 text-primary shrink-0" />
          <span className="font-medium">Execution Goal:</span>
          <span className="text-muted-foreground">{currentSprint.goal}</span>
        </div>
      )}

      {/* Execution Board */}
      <Tabs defaultValue="board" className="space-y-4">
        <TabsList className="h-8">
          <TabsTrigger value="board" className="gap-1.5 text-xs h-7">
            <ListTodo className="h-3.5 w-3.5" />
            Board
          </TabsTrigger>
          <TabsTrigger value="burndown" className="gap-1.5 text-xs h-7">
            <BarChart3 className="h-3.5 w-3.5" />
            Execution Burndown
          </TabsTrigger>
          <TabsTrigger value="velocity" className="gap-1.5 text-xs h-7">
            <TrendingUp className="h-3.5 w-3.5" />
            Velocity
          </TabsTrigger>
        </TabsList>

        <TabsContent value="board">
          {tasksLoading ? (
            <LoadingState message="Loading tasks..." />
          ) : (
            <SprintBoard
              tasks={scopedTasks}
              sprints={sprints || []}
              onTaskUpdate={handleTaskUpdate}
              onTaskCreate={handleTaskCreate}
              onTaskEdit={handleTaskEdit}
              showBacklog={!selectedExecution || selectedExecution === "all" || selectedExecution === "backlog"}
            />
          )}
        </TabsContent>

        <TabsContent value="burndown">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Execution Burndown</CardTitle>
            </CardHeader>
            <CardContent>
              {metrics?.burndown ? <BurndownChart data={metrics.burndown} /> : <BurndownChart data={[]} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="velocity">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Velocity Trend</CardTitle>
            </CardHeader>
            <CardContent>
              {metrics?.velocity_trend ? (
                <VelocityTrendChart values={metrics.velocity_trend} />
              ) : (
                <VelocityTrendChart values={[]} />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Execution Dialog */}
      <Dialog open={createSprintOpen} onOpenChange={setCreateSprintOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Execution from Protocol</DialogTitle>
            <DialogDescription>Generate a new execution sprint from an existing protocol run.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Protocol Run</Label>
              <Select value={selectedProtocolId} onValueChange={setSelectedProtocolId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select protocol run" />
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
                <Label htmlFor="start-date">Start Date</Label>
                <Input
                  id="start-date"
                  type="date"
                  value={sprintStart}
                  onChange={(event) => setSprintStart(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end-date">End Date</Label>
                <Input
                  id="end-date"
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
            <Button onClick={handleCreateSprint} disabled={!selectedProtocolId || selectedProtocolId === "none"}>
              Create Execution
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
