"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
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
  User,
  Calendar,
  Tag,
  MessageSquare,
  Clock,
  X,
  Plus,
} from "lucide-react"
import type {
  AgileTask,
  AgileTaskCreate,
  AgileTaskUpdate,
  TaskType,
  TaskPriority,
  TaskBoardStatus,
  Sprint,
} from "@/lib/api/types"

const taskTypeConfig: Record<TaskType, { icon: typeof Bug; label: string; color: string }> = {
  bug: { icon: Bug, label: "Bug", color: "text-red-500" },
  story: { icon: BookOpen, label: "Story", color: "text-blue-500" },
  task: { icon: CheckSquare, label: "Task", color: "text-green-500" },
  spike: { icon: Zap, label: "Spike", color: "text-purple-500" },
  epic: { icon: Layers, label: "Epic", color: "text-amber-500" },
}

const priorityConfig: Record<TaskPriority, { icon: typeof AlertTriangle; label: string; color: string }> = {
  critical: { icon: AlertTriangle, label: "Critical", color: "text-red-500" },
  high: { icon: ArrowUp, label: "High", color: "text-orange-500" },
  medium: { icon: ArrowRight, label: "Medium", color: "text-yellow-500" },
  low: { icon: ArrowDown, label: "Low", color: "text-blue-500" },
}

const statusOptions: { value: TaskBoardStatus; label: string }[] = [
  { value: "backlog", label: "Backlog" },
  { value: "todo", label: "To Do" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "Review" },
  { value: "testing", label: "Testing" },
  { value: "done", label: "Done" },
]

interface TaskModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  task?: AgileTask | null
  sprints: Sprint[]
  onSave: (data: AgileTaskCreate | AgileTaskUpdate) => Promise<void>
  mode: "create" | "edit" | "view"
}

export function TaskModal({ open, onOpenChange, task, sprints, onSave, mode }: TaskModalProps) {
  const [formData, setFormData] = useState<AgileTaskCreate>({
    title: "",
    description: "",
    task_type: "task",
    priority: "medium",
    board_status: "backlog",
    story_points: undefined,
    assignee: "",
    sprint_id: undefined,
    labels: [],
    acceptance_criteria: [],
    due_date: "",
  })
  const [newLabel, setNewLabel] = useState("")
  const [newCriteria, setNewCriteria] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (task && (mode === "edit" || mode === "view")) {
      setFormData({
        title: task.title,
        description: task.description || "",
        task_type: task.task_type,
        priority: task.priority,
        board_status: task.board_status,
        story_points: task.story_points || undefined,
        assignee: task.assignee || "",
        sprint_id: task.sprint_id || undefined,
        labels: task.labels || [],
        acceptance_criteria: task.acceptance_criteria || [],
        due_date: task.due_date || "",
      })
    } else if (mode === "create") {
      setFormData({
        title: "",
        description: "",
        task_type: "task",
        priority: "medium",
        board_status: "backlog",
        story_points: undefined,
        assignee: "",
        sprint_id: undefined,
        labels: [],
        acceptance_criteria: [],
        due_date: "",
      })
    }
  }, [task, mode, open])

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(formData)
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  const addLabel = () => {
    if (newLabel.trim() && !formData.labels?.includes(newLabel.trim())) {
      setFormData((prev) => ({ ...prev, labels: [...(prev.labels || []), newLabel.trim()] }))
      setNewLabel("")
    }
  }

  const removeLabel = (label: string) => {
    setFormData((prev) => ({ ...prev, labels: prev.labels?.filter((l) => l !== label) || [] }))
  }

  const addCriteria = () => {
    if (newCriteria.trim()) {
      setFormData((prev) => ({
        ...prev,
        acceptance_criteria: [...(prev.acceptance_criteria || []), newCriteria.trim()],
      }))
      setNewCriteria("")
    }
  }

  const removeCriteria = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      acceptance_criteria: prev.acceptance_criteria?.filter((_, i) => i !== index) || [],
    }))
  }

  const isReadOnly = mode === "view"
  const TypeIcon = taskTypeConfig[formData.task_type || "task"].icon

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="3xl" className="max-h-[90vh] p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-muted ${taskTypeConfig[formData.task_type || "task"].color}`}>
              <TypeIcon className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <DialogTitle className="text-xl">
                {mode === "create" ? "Create Task" : mode === "edit" ? "Edit Task" : task?.title}
              </DialogTitle>
              <DialogDescription>
                {mode === "create"
                  ? "Create a new task for your execution board"
                  : mode === "edit"
                    ? "Update task details and properties"
                    : `${taskTypeConfig[formData.task_type || "task"].label} #${task?.id}`}
              </DialogDescription>
            </div>
            {task && (
              <Badge variant="outline" className="font-mono">
                #{task.id}
              </Badge>
            )}
          </div>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh]">
          <Tabs defaultValue="details" className="w-full">
            <div className="px-6 pt-2">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="criteria">Acceptance Criteria</TabsTrigger>
                <TabsTrigger value="activity">Activity</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="details" className="px-6 py-4 space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="col-span-2 space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={formData.title}
                    onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="Enter task title"
                    disabled={isReadOnly}
                    className="font-medium"
                  />
                </div>

                <div className="col-span-2 space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe the task..."
                    disabled={isReadOnly}
                    rows={4}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select
                    value={formData.task_type}
                    onValueChange={(value: TaskType) => setFormData((prev) => ({ ...prev, task_type: value }))}
                    disabled={isReadOnly}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(taskTypeConfig).map(([key, config]) => {
                        const Icon = config.icon
                        return (
                          <SelectItem key={key} value={key}>
                            <div className="flex items-center gap-2">
                              <Icon className={`h-4 w-4 ${config.color}`} />
                              {config.label}
                            </div>
                          </SelectItem>
                        )
                      })}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select
                    value={formData.priority}
                    onValueChange={(value: TaskPriority) => setFormData((prev) => ({ ...prev, priority: value }))}
                    disabled={isReadOnly}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(priorityConfig).map(([key, config]) => {
                        const Icon = config.icon
                        return (
                          <SelectItem key={key} value={key}>
                            <div className="flex items-center gap-2">
                              <Icon className={`h-4 w-4 ${config.color}`} />
                              {config.label}
                            </div>
                          </SelectItem>
                        )
                      })}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select
                    value={formData.board_status}
                    onValueChange={(value: TaskBoardStatus) =>
                      setFormData((prev) => ({ ...prev, board_status: value }))
                    }
                    disabled={isReadOnly}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {statusOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Execution</Label>
                  <Select
                    value={formData.sprint_id?.toString() || "backlog"}
                    onValueChange={(value) =>
                      setFormData((prev) => ({
                        ...prev,
                        sprint_id: value === "backlog" ? undefined : Number.parseInt(value),
                      }))
                    }
                    disabled={isReadOnly}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select execution" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="backlog">Execution Backlog</SelectItem>
                      {sprints.map((sprint) => (
                        <SelectItem key={sprint.id} value={sprint.id.toString()}>
                          {sprint.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {task && (
                  <div className="space-y-2">
                    <Label>Protocol Run</Label>
                    <Input value={task.protocol_run_id ? `#${task.protocol_run_id}` : "Not linked"} disabled />
                  </div>
                )}

                {task && (
                  <div className="space-y-2">
                    <Label>Step Run</Label>
                    <Input value={task.step_run_id ? `#${task.step_run_id}` : "Not linked"} disabled />
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="story_points">Story Points</Label>
                  <Select
                    value={formData.story_points?.toString() || ""}
                    onValueChange={(value) =>
                      setFormData((prev) => ({ ...prev, story_points: value ? Number.parseInt(value) : undefined }))
                    }
                    disabled={isReadOnly}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Estimate" />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 5, 8, 13, 21].map((points) => (
                        <SelectItem key={points} value={points.toString()}>
                          {points} {points === 1 ? "point" : "points"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="assignee">Assignee</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="assignee"
                      value={formData.assignee}
                      onChange={(e) => setFormData((prev) => ({ ...prev, assignee: e.target.value }))}
                      placeholder="Assign to..."
                      disabled={isReadOnly}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="due_date">Due Date</Label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="due_date"
                      type="date"
                      value={formData.due_date}
                      onChange={(e) => setFormData((prev) => ({ ...prev, due_date: e.target.value }))}
                      disabled={isReadOnly}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div className="col-span-2 space-y-2">
                  <Label>Labels</Label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {formData.labels?.map((label) => (
                      <Badge key={label} variant="secondary" className="gap-1">
                        <Tag className="h-3 w-3" />
                        {label}
                        {!isReadOnly && (
                          <button onClick={() => removeLabel(label)} className="ml-1 hover:text-destructive">
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </Badge>
                    ))}
                  </div>
                  {!isReadOnly && (
                    <div className="flex gap-2">
                      <Input
                        value={newLabel}
                        onChange={(e) => setNewLabel(e.target.value)}
                        placeholder="Add label..."
                        onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addLabel())}
                        className="flex-1"
                      />
                      <Button type="button" variant="outline" size="icon" onClick={addLabel}>
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="criteria" className="px-6 py-4 space-y-4">
              <div className="space-y-3">
                {formData.acceptance_criteria?.map((criteria, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 border">
                    <CheckSquare className="h-4 w-4 mt-0.5 text-green-500" />
                    <span className="flex-1 text-sm">{criteria}</span>
                    {!isReadOnly && (
                      <button
                        onClick={() => removeCriteria(index)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
                {formData.acceptance_criteria?.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <CheckSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No acceptance criteria defined</p>
                  </div>
                )}
              </div>
              {!isReadOnly && (
                <div className="flex gap-2">
                  <Textarea
                    value={newCriteria}
                    onChange={(e) => setNewCriteria(e.target.value)}
                    placeholder="Add acceptance criteria..."
                    rows={2}
                    className="flex-1"
                  />
                  <Button type="button" variant="outline" onClick={addCriteria} className="self-end bg-transparent">
                    <Plus className="h-4 w-4 mr-2" />
                    Add
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="activity" className="px-6 py-4">
              <div className="space-y-4">
                {task ? (
                  <>
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-full bg-muted">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm">Task created</p>
                        <p className="text-xs text-muted-foreground">{new Date(task.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    {task.started_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-full bg-blue-500/10">
                          <ArrowRight className="h-4 w-4 text-blue-500" />
                        </div>
                        <div>
                          <p className="text-sm">Work started</p>
                          <p className="text-xs text-muted-foreground">{new Date(task.started_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                    {task.completed_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-full bg-green-500/10">
                          <CheckSquare className="h-4 w-4 text-green-500" />
                        </div>
                        <div>
                          <p className="text-sm">Task completed</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(task.completed_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>Activity will appear here after the task is created</p>
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </ScrollArea>

        <DialogFooter className="px-6 py-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {isReadOnly ? "Close" : "Cancel"}
          </Button>
          {!isReadOnly && (
            <Button onClick={handleSave} disabled={saving || !formData.title.trim()}>
              {saving ? "Saving..." : mode === "create" ? "Create Task" : "Save Changes"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
