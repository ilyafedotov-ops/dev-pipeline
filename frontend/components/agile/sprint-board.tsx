"use client";

import type React from "react";
import { useCallback, useEffect, useState } from "react";

import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Bug,
  CheckSquare,
  Eye,
  GripVertical,
  Layers,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  Trash2,
  User,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type {
  AgileTask,
  AgileTaskCreate,
  AgileTaskUpdate,
  Sprint,
  TaskBoardStatus,
  TaskPriority,
  TaskType,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { MobileKanbanView } from "./mobile-kanban-view";
import { TaskModal } from "./task-modal";

// Mobile breakpoint (matches Tailwind's md breakpoint)
const MOBILE_BREAKPOINT = 768;

// Hook to detect mobile screen size
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Check initial screen size
    const checkMobile = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };

    // Set initial value
    checkMobile();

    // Listen for resize events
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  return isMobile;
}

const taskTypeConfig: Record<TaskType, { icon: typeof Bug; color: string; bg: string }> = {
  bug: { icon: Bug, color: "text-red-500", bg: "bg-red-500/10" },
  story: { icon: BookOpen, color: "text-blue-500", bg: "bg-blue-500/10" },
  task: { icon: CheckSquare, color: "text-green-500", bg: "bg-green-500/10" },
  spike: { icon: Zap, color: "text-purple-500", bg: "bg-purple-500/10" },
  epic: { icon: Layers, color: "text-amber-500", bg: "bg-amber-500/10" },
};

const priorityConfig: Record<TaskPriority, { icon: typeof AlertTriangle; color: string }> = {
  critical: { icon: AlertTriangle, color: "text-red-500" },
  high: { icon: ArrowUp, color: "text-orange-500" },
  medium: { icon: ArrowRight, color: "text-yellow-500" },
  low: { icon: ArrowDown, color: "text-blue-400" },
};

const columns: { id: TaskBoardStatus; title: string; color: string }[] = [
  { id: "backlog", title: "Backlog", color: "border-t-slate-500" },
  { id: "todo", title: "To Do", color: "border-t-blue-500" },
  { id: "in_progress", title: "In Progress", color: "border-t-amber-500" },
  { id: "review", title: "Review", color: "border-t-purple-500" },
  { id: "testing", title: "Testing", color: "border-t-cyan-500" },
  { id: "done", title: "Done", color: "border-t-green-500" },
];

interface SprintBoardProps {
  tasks: AgileTask[];
  sprints: Sprint[];
  onTaskUpdate: (taskId: number, data: { board_status: TaskBoardStatus }) => Promise<void>;
  onTaskCreate: (data: AgileTaskCreate) => Promise<void>;
  onTaskEdit: (taskId: number, data: AgileTaskUpdate) => Promise<void>;
  onTaskDelete?: (taskId: number) => Promise<void>;
  showBacklog?: boolean;
  canCreate?: boolean;
  onTaskExecute?: (taskId: number) => Promise<void>;
}

export function SprintBoard({
  tasks,
  sprints,
  onTaskUpdate,
  onTaskCreate,
  onTaskEdit,
  onTaskDelete,
  showBacklog = true,
  canCreate = true,
  onTaskExecute,
}: SprintBoardProps) {
  const [draggedTask, setDraggedTask] = useState<AgileTask | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<TaskBoardStatus | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | "edit" | "view">("create");
  const [selectedTask, setSelectedTask] = useState<AgileTask | null>(null);
  const [confirmExecute, setConfirmExecute] = useState<{
    task: AgileTask;
    targetStatus: TaskBoardStatus;
  } | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);

  const isMobile = useIsMobile();

  const visibleColumns = showBacklog ? columns : columns.filter((c) => c.id !== "backlog");

  const getTasksByColumn = useCallback(
    (status: TaskBoardStatus) => {
      return tasks.filter((task) => task.board_status === status);
    },
    [tasks]
  );

  const handleDragStart = (e: React.DragEvent, task: AgileTask) => {
    setDraggedTask(task);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", task.id.toString());
  };

  const handleDragOver = (e: React.DragEvent, status: TaskBoardStatus) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverColumn(status);
  };

  const handleDragLeave = () => {
    setDragOverColumn(null);
  };

  const handleDrop = async (e: React.DragEvent, status: TaskBoardStatus) => {
    e.preventDefault();
    setDragOverColumn(null);
    if (draggedTask && draggedTask.board_status !== status) {
      if (status === "in_progress" && onTaskExecute) {
        setConfirmExecute({ task: draggedTask, targetStatus: status });
        setDraggedTask(null);
        return;
      }
      try {
        await onTaskUpdate(draggedTask.id, { board_status: status });
        toast.success(`Task moved to ${columns.find((c) => c.id === status)?.title}`);
      } catch {
        toast.error("Failed to move task");
      }
    }
    setDraggedTask(null);
  };

  const handleDragEnd = () => {
    setDraggedTask(null);
    setDragOverColumn(null);
  };

  const openCreateModal = () => {
    setSelectedTask(null);
    setModalMode("create");
    setModalOpen(true);
  };

  const openViewModal = (task: AgileTask) => {
    setSelectedTask(task);
    setModalMode("view");
    setModalOpen(true);
  };

  const openEditModal = (task: AgileTask) => {
    setSelectedTask(task);
    setModalMode("edit");
    setModalOpen(true);
  };

  const handleModalSave = async (data: AgileTaskCreate | AgileTaskUpdate) => {
    if (modalMode === "create") {
      await onTaskCreate(data as AgileTaskCreate);
    } else if (modalMode === "edit" && selectedTask) {
      await onTaskEdit(selectedTask.id, data as AgileTaskUpdate);
    }
  };

  const getColumnStats = (status: TaskBoardStatus) => {
    const columnTasks = getTasksByColumn(status);
    const totalPoints = columnTasks.reduce((acc, t) => acc + (t.story_points || 0), 0);
    return { count: columnTasks.length, points: totalPoints };
  };

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold">Execution Board</h3>
          <div className="text-muted-foreground flex items-center gap-2 text-xs">
            <span>{tasks.length} tasks</span>
            <Separator orientation="vertical" className="h-4" />
            <span>{tasks.reduce((acc, t) => acc + (t.story_points || 0), 0)} points</span>
          </div>
        </div>
        <Button size="sm" onClick={() => canCreate && openCreateModal()} disabled={!canCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Task
        </Button>
      </div>

      {/* Mobile view */}
      {isMobile ? (
        <MobileKanbanView
          tasks={tasks}
          columns={visibleColumns}
          onTaskUpdate={onTaskUpdate}
          onTaskView={openViewModal}
          onTaskEdit={openEditModal}
          showBacklog={showBacklog}
        />
      ) : (
        /* Desktop view */
        <ScrollArea className="w-full">
          <div className="flex gap-4 pb-4" style={{ minWidth: visibleColumns.length * 280 }}>
            {visibleColumns.map((column) => {
              const stats = getColumnStats(column.id);
              const columnTasks = getTasksByColumn(column.id);
              const isDropTarget = dragOverColumn === column.id;

              return (
                <div
                  key={column.id}
                  className={cn(
                    "bg-muted/30 max-w-[320px] min-w-[260px] flex-1 rounded-lg border border-t-4 transition-colors",
                    column.color,
                    isDropTarget && "ring-primary bg-primary/5 ring-2 ring-offset-2"
                  )}
                  onDragOver={(e) => handleDragOver(e, column.id)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, column.id)}
                >
                  <div className="bg-muted/50 border-b p-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium">{column.title}</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                          {stats.count}
                        </Badge>
                        {stats.points > 0 && (
                          <Badge variant="outline" className="h-5 px-1.5 text-xs">
                            {stats.points}pt
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>

                  <ScrollArea className="h-[calc(100vh-380px)] min-h-[400px]">
                    <div className="space-y-2 p-2">
                      {columnTasks.map((task) => {
                        const TypeIcon = taskTypeConfig[task.task_type].icon;
                        const PriorityIcon = priorityConfig[task.priority].icon;
                        const isDragging = draggedTask?.id === task.id;

                        return (
                          <div
                            key={task.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, task)}
                            onDragEnd={handleDragEnd}
                            className={cn(
                              "group bg-card cursor-grab rounded-md border p-3 shadow-sm transition-all hover:shadow-md active:cursor-grabbing",
                              isDragging && "scale-95 opacity-50"
                            )}
                          >
                            <div className="flex items-start gap-2">
                              <GripVertical className="text-muted-foreground mt-0.5 h-4 w-4 shrink-0 opacity-0 group-hover:opacity-100" />
                              <div className="min-w-0 flex-1">
                                <div className="mb-2 flex items-start justify-between gap-2">
                                  <div className="flex items-center gap-1.5">
                                    <div
                                      className={cn(
                                        "rounded p-1",
                                        taskTypeConfig[task.task_type].bg
                                      )}
                                    >
                                      <TypeIcon
                                        className={cn(
                                          "h-3 w-3",
                                          taskTypeConfig[task.task_type].color
                                        )}
                                      />
                                    </div>
                                    <span className="text-muted-foreground font-mono text-xs">
                                      #{task.id}
                                    </span>
                                    {task.protocol_run_id && (
                                      <span className="text-muted-foreground text-[10px]">
                                        PR#{task.protocol_run_id}
                                      </span>
                                    )}
                                    {task.step_run_id && (
                                      <span className="text-muted-foreground text-[10px]">
                                        S#{task.step_run_id}
                                      </span>
                                    )}
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
                                        <Eye className="mr-2 h-4 w-4" />
                                        View
                                      </DropdownMenuItem>
                                      <DropdownMenuItem onClick={() => openEditModal(task)}>
                                        <Pencil className="mr-2 h-4 w-4" />
                                        Edit
                                      </DropdownMenuItem>
                                      <DropdownMenuItem className="text-destructive">
                                        <Trash2 className="mr-2 h-4 w-4" />
                                        Delete
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </div>

                                <button
                                  type="button"
                                  className="hover:text-primary mb-2 line-clamp-2 w-full text-left text-sm font-medium"
                                  onClick={() => openViewModal(task)}
                                >
                                  {task.title}
                                </button>

                                <div className="mb-2 flex flex-wrap gap-1">
                                  {task.labels.slice(0, 2).map((label) => (
                                    <Badge
                                      key={label}
                                      variant="outline"
                                      className="h-4 px-1 text-[10px]"
                                    >
                                      {label}
                                    </Badge>
                                  ))}
                                  {task.labels.length > 2 && (
                                    <Badge variant="outline" className="h-4 px-1 text-[10px]">
                                      +{task.labels.length - 2}
                                    </Badge>
                                  )}
                                </div>

                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <PriorityIcon
                                      className={cn("h-3 w-3", priorityConfig[task.priority].color)}
                                    />
                                    {task.story_points && (
                                      <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
                                        {task.story_points}pt
                                      </Badge>
                                    )}
                                  </div>
                                  {task.assignee && (
                                    <div className="text-muted-foreground flex items-center gap-1 text-xs">
                                      <div className="bg-primary/10 flex h-5 w-5 items-center justify-center rounded-full">
                                        <User className="h-3 w-3" />
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      {columnTasks.length === 0 && (
                        <div className="text-muted-foreground py-8 text-center">
                          <p className="text-xs">No tasks</p>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              );
            })}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      )}

      <TaskModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        task={selectedTask}
        sprints={sprints}
        onSave={handleModalSave}
        onDelete={onTaskDelete}
        mode={modalMode}
      />

      {/* Execution Confirmation Dialog */}
      <Dialog
        open={!!confirmExecute}
        onOpenChange={(open) => {
          if (!open) setConfirmExecute(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Start Task Execution</DialogTitle>
            <DialogDescription>
              Do you want to start implementation for &quot;{confirmExecute?.task.title}&quot;?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <div className="flex w-full flex-col gap-2">
              <Button
                className="w-full"
                disabled={isExecuting}
                onClick={async () => {
                  if (!confirmExecute) return;
                  setIsExecuting(true);
                  try {
                    await onTaskUpdate(confirmExecute.task.id, {
                      board_status: confirmExecute.targetStatus,
                    });
                    await onTaskExecute!(confirmExecute.task.id);
                    toast.success(`Execution started for "${confirmExecute.task.title}"`);
                  } catch {
                    toast.error("Failed to start execution");
                  } finally {
                    setIsExecuting(false);
                    setConfirmExecute(null);
                  }
                }}
              >
                <Play className="mr-2 h-4 w-4" />
                {isExecuting ? "Starting..." : "Start Execution"}
              </Button>
              <Button
                variant="secondary"
                className="w-full"
                disabled={isExecuting}
                onClick={async () => {
                  if (!confirmExecute) return;
                  try {
                    await onTaskUpdate(confirmExecute.task.id, {
                      board_status: confirmExecute.targetStatus,
                    });
                    toast.success(
                      `Task moved to ${columns.find((c) => c.id === confirmExecute.targetStatus)?.title}`
                    );
                  } catch {
                    toast.error("Failed to move task");
                  } finally {
                    setConfirmExecute(null);
                  }
                }}
              >
                Move Only
              </Button>
              <Button
                variant="outline"
                className="w-full"
                disabled={isExecuting}
                onClick={() => setConfirmExecute(null)}
              >
                Cancel
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
