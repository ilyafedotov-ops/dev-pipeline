"use client";

import type React from "react";
import { useCallback,useRef, useState } from "react";

import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Bug,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Eye,
  Layers,
  MoreHorizontal,
  Pencil,
  Trash2,
  User,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent,TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  AgileTask,
  TaskBoardStatus,
  TaskPriority,
  TaskType,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

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

export interface KanbanColumn {
  id: TaskBoardStatus;
  title: string;
  color: string;
}

const defaultColumns: KanbanColumn[] = [
  { id: "backlog", title: "Backlog", color: "border-t-slate-500" },
  { id: "todo", title: "To Do", color: "border-t-blue-500" },
  { id: "in_progress", title: "In Progress", color: "border-t-amber-500" },
  { id: "review", title: "Review", color: "border-t-purple-500" },
  { id: "testing", title: "Testing", color: "border-t-cyan-500" },
  { id: "done", title: "Done", color: "border-t-green-500" },
];

interface MobileKanbanViewProps {
  tasks: AgileTask[];
  columns?: KanbanColumn[];
  onTaskUpdate: (taskId: number, data: { board_status: TaskBoardStatus }) => Promise<void>;
  onTaskView?: (task: AgileTask) => void;
  onTaskEdit?: (task: AgileTask) => void;
  onTaskDelete?: (task: AgileTask) => void;
  showBacklog?: boolean;
}

// Swipe detection threshold in pixels
const SWIPE_THRESHOLD = 50;

export function MobileKanbanView({
  tasks,
  columns = defaultColumns,
  onTaskUpdate,
  onTaskView,
  onTaskEdit,
  onTaskDelete,
  showBacklog = true,
}: MobileKanbanViewProps) {
  const visibleColumns = showBacklog ? columns : columns.filter((c) => c.id !== "backlog");
  const [activeColumn, setActiveColumn] = useState<TaskBoardStatus>(
    visibleColumns[0]?.id || "todo"
  );

  // Swipe gesture state
  const touchStartX = useRef<number>(0);
  const touchEndX = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const getTasksByColumn = useCallback(
    (status: TaskBoardStatus) => {
      return tasks.filter((task) => task.board_status === status);
    },
    [tasks]
  );

  const getColumnStats = (status: TaskBoardStatus) => {
    const columnTasks = getTasksByColumn(status);
    const totalPoints = columnTasks.reduce((acc, t) => acc + (t.story_points || 0), 0);
    return { count: columnTasks.length, points: totalPoints };
  };

  const currentColumnIndex = visibleColumns.findIndex((c) => c.id === activeColumn);

  const navigateToColumn = (direction: "prev" | "next") => {
    const newIndex =
      direction === "prev"
        ? Math.max(0, currentColumnIndex - 1)
        : Math.min(visibleColumns.length - 1, currentColumnIndex + 1);
    setActiveColumn(visibleColumns[newIndex].id);
  };

  // Touch event handlers for swipe gestures
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    touchEndX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = () => {
    const swipeDistance = touchStartX.current - touchEndX.current;

    if (Math.abs(swipeDistance) > SWIPE_THRESHOLD) {
      if (swipeDistance > 0) {
        // Swiped left - go to next column
        navigateToColumn("next");
      } else {
        // Swiped right - go to previous column
        navigateToColumn("prev");
      }
    }

    // Reset touch positions
    touchStartX.current = 0;
    touchEndX.current = 0;
  };

  const handleMoveTask = async (task: AgileTask, newStatus: TaskBoardStatus) => {
    if (task.board_status !== newStatus) {
      await onTaskUpdate(task.id, { board_status: newStatus });
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Column navigation header */}
      <div className="bg-muted/30 flex items-center justify-between border-b px-2 py-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigateToColumn("prev")}
          disabled={currentColumnIndex === 0}
          className="h-8 w-8"
          aria-label="Previous column"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{visibleColumns[currentColumnIndex]?.title}</span>
          <Badge variant="secondary" className="text-xs">
            {getColumnStats(activeColumn).count}
          </Badge>
          {getColumnStats(activeColumn).points > 0 && (
            <Badge variant="outline" className="text-xs">
              {getColumnStats(activeColumn).points}pt
            </Badge>
          )}
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigateToColumn("next")}
          disabled={currentColumnIndex === visibleColumns.length - 1}
          className="h-8 w-8"
          aria-label="Next column"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Column indicator dots */}
      <div className="flex justify-center gap-1.5 border-b py-2">
        {visibleColumns.map((column, index) => (
          <button
            key={column.id}
            onClick={() => setActiveColumn(column.id)}
            className={cn(
              "h-2 w-2 rounded-full transition-colors",
              index === currentColumnIndex ? "bg-primary" : "bg-muted-foreground/30"
            )}
            aria-label={`Go to ${column.title}`}
          />
        ))}
      </div>

      {/* Tabbed content with swipe support */}
      <Tabs
        value={activeColumn}
        onValueChange={(v) => setActiveColumn(v as TaskBoardStatus)}
        className="flex-1"
      >
        <TabsList className="sr-only">
          {visibleColumns.map((column) => (
            <TabsTrigger key={column.id} value={column.id}>
              {column.title}
            </TabsTrigger>
          ))}
        </TabsList>

        {visibleColumns.map((column) => (
          <TabsContent key={column.id} value={column.id} className="mt-0 flex-1">
            <div
              ref={containerRef}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
              className="h-full"
            >
              <ScrollArea className="h-[calc(100vh-280px)]">
                <div className="space-y-3 p-3">
                  {getTasksByColumn(column.id).map((task) => (
                    <MobileTaskCard
                      key={task.id}
                      task={task}
                      columns={visibleColumns}
                      currentColumn={column.id}
                      onView={onTaskView}
                      onEdit={onTaskEdit}
                      onDelete={onTaskDelete}
                      onMove={handleMoveTask}
                    />
                  ))}

                  {getTasksByColumn(column.id).length === 0 && (
                    <div className="text-muted-foreground py-12 text-center">
                      <p className="text-sm">No tasks in {column.title}</p>
                      <p className="mt-1 text-xs">Swipe to view other columns</p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

// Mobile task card component
interface MobileTaskCardProps {
  task: AgileTask;
  columns: KanbanColumn[];
  currentColumn: TaskBoardStatus;
  onView?: (task: AgileTask) => void;
  onEdit?: (task: AgileTask) => void;
  onDelete?: (task: AgileTask) => void;
  onMove: (task: AgileTask, newStatus: TaskBoardStatus) => Promise<void>;
}

function MobileTaskCard({
  task,
  columns,
  currentColumn,
  onView,
  onEdit,
  onDelete,
  onMove,
}: MobileTaskCardProps) {
  const TypeIcon = taskTypeConfig[task.task_type].icon;
  const PriorityIcon = priorityConfig[task.priority].icon;
  const currentIndex = columns.findIndex((c) => c.id === currentColumn);

  return (
    <div className="bg-card rounded-lg border p-4 shadow-sm">
      {/* Header row */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className={cn("rounded p-1.5", taskTypeConfig[task.task_type].bg)}>
            <TypeIcon className={cn("h-4 w-4", taskTypeConfig[task.task_type].color)} />
          </div>
          <span className="text-muted-foreground font-mono text-xs">#{task.id}</span>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {onView && (
              <DropdownMenuItem onClick={() => onView(task)}>
                <Eye className="mr-2 h-4 w-4" />
                View
              </DropdownMenuItem>
            )}
            {onEdit && (
              <DropdownMenuItem onClick={() => onEdit(task)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
            )}
            {onDelete && (
              <DropdownMenuItem className="text-destructive" onClick={() => onDelete(task)}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Title */}
      <button
        type="button"
        className="hover:text-primary mb-3 w-full text-left text-sm font-medium"
        onClick={() => onView?.(task)}
      >
        {task.title}
      </button>

      {/* Labels */}
      {task.labels.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {task.labels.slice(0, 3).map((label) => (
            <Badge key={label} variant="outline" className="text-xs">
              {label}
            </Badge>
          ))}
          {task.labels.length > 3 && (
            <Badge variant="outline" className="text-xs">
              +{task.labels.length - 3}
            </Badge>
          )}
        </div>
      )}

      {/* Meta row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PriorityIcon className={cn("h-4 w-4", priorityConfig[task.priority].color)} />
          {task.story_points && (
            <Badge variant="secondary" className="text-xs">
              {task.story_points}pt
            </Badge>
          )}
        </div>
        {task.assignee && (
          <div className="text-muted-foreground flex items-center gap-1 text-xs">
            <div className="bg-primary/10 flex h-6 w-6 items-center justify-center rounded-full">
              <User className="h-3 w-3" />
            </div>
            <span className="max-w-[80px] truncate">{task.assignee}</span>
          </div>
        )}
      </div>

      {/* Move buttons */}
      <div className="flex gap-2 border-t pt-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={currentIndex === 0}
          onClick={() => onMove(task, columns[currentIndex - 1]?.id)}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          {currentIndex > 0 ? columns[currentIndex - 1].title : ""}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={currentIndex === columns.length - 1}
          onClick={() => onMove(task, columns[currentIndex + 1]?.id)}
        >
          {currentIndex < columns.length - 1 ? columns[currentIndex + 1].title : ""}
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
