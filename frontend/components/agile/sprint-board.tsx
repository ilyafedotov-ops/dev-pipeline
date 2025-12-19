"use client"

import type React from "react"

import { useState, useCallback } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import {
  Bug,
  BookOpen,
  Zap,
  CheckSquare,
  Layers,
  AlertTriangle,
  ArrowUp,
  ArrowRight,
  ArrowDown,
  MoreHorizontal,
  Plus,
  User,
  GripVertical,
  Eye,
  Pencil,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { AgileTask, AgileTaskCreate, AgileTaskUpdate, TaskType, TaskPriority, TaskBoardStatus, Sprint } from "@/lib/api/types"
import { TaskModal } from "./task-modal"
import { toast } from "sonner"

const taskTypeConfig: Record<TaskType, { icon: typeof Bug; color: string; bg: string }> = {
  bug: { icon: Bug, color: "text-red-500", bg: "bg-red-500/10" },
  story: { icon: BookOpen, color: "text-blue-500", bg: "bg-blue-500/10" },
  task: { icon: CheckSquare, color: "text-green-500", bg: "bg-green-500/10" },
  spike: { icon: Zap, color: "text-purple-500", bg: "bg-purple-500/10" },
  epic: { icon: Layers, color: "text-amber-500", bg: "bg-amber-500/10" },
}

const priorityConfig: Record<TaskPriority, { icon: typeof AlertTriangle; color: string }> = {
  critical: { icon: AlertTriangle, color: "text-red-500" },
  high: { icon: ArrowUp, color: "text-orange-500" },
  medium: { icon: ArrowRight, color: "text-yellow-500" },
  low: { icon: ArrowDown, color: "text-blue-400" },
}

const columns: { id: TaskBoardStatus; title: string; color: string }[] = [
  { id: "backlog", title: "Backlog", color: "border-t-slate-500" },
  { id: "todo", title: "To Do", color: "border-t-blue-500" },
  { id: "in_progress", title: "In Progress", color: "border-t-amber-500" },
  { id: "review", title: "Review", color: "border-t-purple-500" },
  { id: "testing", title: "Testing", color: "border-t-cyan-500" },
  { id: "done", title: "Done", color: "border-t-green-500" },
]

interface SprintBoardProps {
  tasks: AgileTask[]
  sprints: Sprint[]
  onTaskUpdate: (taskId: number, data: { board_status: TaskBoardStatus }) => Promise<void>
  onTaskCreate: (data: AgileTaskCreate) => Promise<void>
  onTaskEdit: (taskId: number, data: AgileTaskUpdate) => Promise<void>
  showBacklog?: boolean
}

export function SprintBoard({
  tasks,
  sprints,
  onTaskUpdate,
  onTaskCreate,
  onTaskEdit,
  showBacklog = true,
}: SprintBoardProps) {
  const [draggedTask, setDraggedTask] = useState<AgileTask | null>(null)
  const [dragOverColumn, setDragOverColumn] = useState<TaskBoardStatus | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<"create" | "edit" | "view">("create")
  const [selectedTask, setSelectedTask] = useState<AgileTask | null>(null)

  const visibleColumns = showBacklog ? columns : columns.filter((c) => c.id !== "backlog")

  const getTasksByColumn = useCallback(
    (status: TaskBoardStatus) => {
      return tasks.filter((task) => task.board_status === status)
    },
    [tasks],
  )

  const handleDragStart = (e: React.DragEvent, task: AgileTask) => {
    setDraggedTask(task)
    e.dataTransfer.effectAllowed = "move"
    e.dataTransfer.setData("text/plain", task.id.toString())
  }

  const handleDragOver = (e: React.DragEvent, status: TaskBoardStatus) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    setDragOverColumn(status)
  }

  const handleDragLeave = () => {
    setDragOverColumn(null)
  }

  const handleDrop = async (e: React.DragEvent, status: TaskBoardStatus) => {
    e.preventDefault()
    setDragOverColumn(null)

    if (draggedTask && draggedTask.board_status !== status) {
      try {
        await onTaskUpdate(draggedTask.id, { board_status: status })
        toast.success(`Task moved to ${columns.find((c) => c.id === status)?.title}`)
      } catch {
        toast.error("Failed to move task")
      }
    }
    setDraggedTask(null)
  }

  const handleDragEnd = () => {
    setDraggedTask(null)
    setDragOverColumn(null)
  }

  const openCreateModal = () => {
    setSelectedTask(null)
    setModalMode("create")
    setModalOpen(true)
  }

  const openViewModal = (task: AgileTask) => {
    setSelectedTask(task)
    setModalMode("view")
    setModalOpen(true)
  }

  const openEditModal = (task: AgileTask) => {
    setSelectedTask(task)
    setModalMode("edit")
    setModalOpen(true)
  }

  const handleModalSave = async (data: AgileTaskCreate | AgileTaskUpdate) => {
    if (modalMode === "create") {
      await onTaskCreate(data as AgileTaskCreate)
    } else if (modalMode === "edit" && selectedTask) {
      await onTaskEdit(selectedTask.id, data as AgileTaskUpdate)
    }
  }

  const getColumnStats = (status: TaskBoardStatus) => {
    const columnTasks = getTasksByColumn(status)
    const totalPoints = columnTasks.reduce((acc, t) => acc + (t.story_points || 0), 0)
    return { count: columnTasks.length, points: totalPoints }
  }

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold">Sprint Board</h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{tasks.length} tasks</span>
            <Separator orientation="vertical" className="h-4" />
            <span>{tasks.reduce((acc, t) => acc + (t.story_points || 0), 0)} points</span>
          </div>
        </div>
        <Button size="sm" onClick={() => openCreateModal()}>
          <Plus className="h-4 w-4 mr-2" />
          Add Task
        </Button>
      </div>

      <ScrollArea className="w-full">
        <div className="flex gap-4 pb-4" style={{ minWidth: visibleColumns.length * 280 }}>
          {visibleColumns.map((column) => {
            const stats = getColumnStats(column.id)
            const columnTasks = getTasksByColumn(column.id)
            const isDropTarget = dragOverColumn === column.id

            return (
              <div
                key={column.id}
                className={cn(
                  "flex-1 min-w-[260px] max-w-[320px] rounded-lg border border-t-4 bg-muted/30 transition-colors",
                  column.color,
                  isDropTarget && "ring-2 ring-primary ring-offset-2 bg-primary/5",
                )}
                onDragOver={(e) => handleDragOver(e, column.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, column.id)}
              >
                <div className="p-3 border-b bg-muted/50">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium text-sm">{column.title}</h4>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs h-5 px-1.5">
                        {stats.count}
                      </Badge>
                      {stats.points > 0 && (
                        <Badge variant="outline" className="text-xs h-5 px-1.5">
                          {stats.points}pt
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <ScrollArea className="h-[calc(100vh-380px)] min-h-[400px]">
                  <div className="p-2 space-y-2">
                    {columnTasks.map((task) => {
                      const TypeIcon = taskTypeConfig[task.task_type].icon
                      const PriorityIcon = priorityConfig[task.priority].icon
                      const isDragging = draggedTask?.id === task.id

                      return (
                        <div
                          key={task.id}
                          draggable
                          onDragStart={(e) => handleDragStart(e, task)}
                          onDragEnd={handleDragEnd}
                          className={cn(
                            "group p-3 rounded-md border bg-card shadow-sm cursor-grab active:cursor-grabbing transition-all hover:shadow-md",
                            isDragging && "opacity-50 scale-95",
                          )}
                        >
                          <div className="flex items-start gap-2">
                            <GripVertical className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 mt-0.5 shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="flex items-center gap-1.5">
                                  <div className={cn("p-1 rounded", taskTypeConfig[task.task_type].bg)}>
                                    <TypeIcon className={cn("h-3 w-3", taskTypeConfig[task.task_type].color)} />
                                  </div>
                                  <span className="text-xs font-mono text-muted-foreground">#{task.id}</span>
                                </div>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                                    >
                                      <MoreHorizontal className="h-3 w-3" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={() => openViewModal(task)}>
                                      <Eye className="h-4 w-4 mr-2" />
                                      View
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => openEditModal(task)}>
                                      <Pencil className="h-4 w-4 mr-2" />
                                      Edit
                                    </DropdownMenuItem>
                                    <DropdownMenuItem className="text-destructive">
                                      <Trash2 className="h-4 w-4 mr-2" />
                                      Delete
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>

                              <p
                                className="text-sm font-medium line-clamp-2 mb-2 cursor-pointer hover:text-primary"
                                onClick={() => openViewModal(task)}
                              >
                                {task.title}
                              </p>

                              <div className="flex flex-wrap gap-1 mb-2">
                                {task.labels.slice(0, 2).map((label) => (
                                  <Badge key={label} variant="outline" className="text-[10px] h-4 px-1">
                                    {label}
                                  </Badge>
                                ))}
                                {task.labels.length > 2 && (
                                  <Badge variant="outline" className="text-[10px] h-4 px-1">
                                    +{task.labels.length - 2}
                                  </Badge>
                                )}
                              </div>

                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <PriorityIcon className={cn("h-3 w-3", priorityConfig[task.priority].color)} />
                                  {task.story_points && (
                                    <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
                                      {task.story_points}pt
                                    </Badge>
                                  )}
                                </div>
                                {task.assignee && (
                                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <div className="h-5 w-5 rounded-full bg-primary/10 flex items-center justify-center">
                                      <User className="h-3 w-3" />
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}

                    {columnTasks.length === 0 && (
                      <div className="py-8 text-center text-muted-foreground">
                        <p className="text-xs">No tasks</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            )
          })}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>

      <TaskModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        task={selectedTask}
        sprints={sprints}
        onSave={handleModalSave}
        mode={modalMode}
      />
    </>
  )
}
