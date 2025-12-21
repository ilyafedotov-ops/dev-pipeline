"use client"

import * as React from "react"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    FileText,
    ClipboardList,
    ListTodo,
    Kanban,
    CheckCircle2,
    Circle,
    ArrowRight,
    Loader2,
    Play,
    MessageSquare,
    ClipboardCheck,
    FileSearch,
    PlayCircle,
} from "lucide-react"

export type WorkflowStep =
    | "spec"
    | "clarify"
    | "plan"
    | "checklist"
    | "tasks"
    | "analyze"
    | "implement"
    | "sprint"
export type StepStatus = "pending" | "in-progress" | "completed"

interface SpecWorkflowProps {
    projectId: number
    currentStep?: WorkflowStep
    /** Status for each step */
    stepStatus?: {
        spec?: StepStatus
        clarify?: StepStatus
        plan?: StepStatus
        checklist?: StepStatus
        tasks?: StepStatus
        analyze?: StepStatus
        implement?: StepStatus
        sprint?: StepStatus
    }
    /** Show action buttons for next steps */
    showActions?: boolean
    /** Compact mode for inline display */
    compact?: boolean
    className?: string
}

const steps: { key: WorkflowStep; label: string; icon: React.ElementType; description: string }[] = [
    {
        key: "spec",
        label: "Specification",
        icon: FileText,
        description: "Define feature requirements",
    },
    {
        key: "clarify",
        label: "Clarify",
        icon: MessageSquare,
        description: "Resolve ambiguity",
    },
    {
        key: "plan",
        label: "Implementation Plan",
        icon: ClipboardList,
        description: "Design architecture & approach",
    },
    {
        key: "checklist",
        label: "Checklist",
        icon: ClipboardCheck,
        description: "Validate requirements",
    },
    {
        key: "tasks",
        label: "Task List",
        icon: ListTodo,
        description: "Break down into tasks",
    },
    {
        key: "analyze",
        label: "Analyze",
        icon: FileSearch,
        description: "Consistency report",
    },
    {
        key: "implement",
        label: "Implement",
        icon: PlayCircle,
        description: "Initialize execution",
    },
    {
        key: "sprint",
        label: "Execution",
        icon: Kanban,
        description: "Assign to execution cycle",
    },
]

function getStepHref(step: WorkflowStep, projectId: number): string {
    switch (step) {
        case "spec":
            return `/projects/${projectId}?wizard=generate-specs`
        case "clarify":
            return `/projects/${projectId}?tab=spec`
        case "plan":
            return `/projects/${projectId}?wizard=design-solution`
        case "checklist":
            return `/projects/${projectId}?tab=spec`
        case "tasks":
            return `/projects/${projectId}?wizard=implement-feature`
        case "analyze":
            return `/projects/${projectId}?tab=spec`
        case "implement":
            return `/projects/${projectId}?tab=spec`
        case "sprint":
            return `/projects/${projectId}/execution`
        default:
            return `/projects/${projectId}`
    }
}

function getStatusIcon(status: StepStatus | undefined, isActive: boolean) {
    switch (status) {
        case "completed":
            return <CheckCircle2 className="h-5 w-5 text-green-500" />
        case "in-progress":
            return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
        default:
            return isActive ? (
                <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                    <Play className="h-3 w-3 text-primary-foreground" />
                </div>
            ) : (
                <Circle className="h-5 w-5 text-muted-foreground" />
            )
    }
}

function getStatusColor(status: StepStatus | undefined, isActive: boolean): string {
    if (status === "completed") return "border-green-500 bg-green-500/10"
    if (status === "in-progress") return "border-blue-500 bg-blue-500/10"
    if (isActive) return "border-primary bg-primary/10"
    return "border-muted"
}

/**
 * SpecWorkflow - Visual stepper component showing the SpecKit workflow pipeline
 * 
 * Shows the SpecKit workflow: Specification → Clarify → Plan → Checklist → Tasks → Analyze → Implement → Execution
 * Each step shows its status and provides navigation to the relevant page.
 */
export function SpecWorkflow({
    projectId,
    currentStep,
    stepStatus = {},
    showActions = true,
    compact = false,
    className,
}: SpecWorkflowProps) {
    if (compact) {
        // Compact inline version for cards/headers
        return (
            <div className={cn("flex items-center gap-2", className)}>
                {steps.map((step, index) => {
                    const status = stepStatus[step.key]
                    const isActive = currentStep === step.key
                    const Icon = step.icon

                    return (
                        <React.Fragment key={step.key}>
                            <Link
                                href={getStepHref(step.key, projectId)}
                                className={cn(
                                    "flex items-center gap-1.5 px-2 py-1 rounded-md text-sm transition-colors",
                                    status === "completed"
                                        ? "text-green-600 hover:bg-green-500/10"
                                        : status === "in-progress"
                                            ? "text-blue-600 hover:bg-blue-500/10"
                                            : isActive
                                                ? "text-primary font-medium hover:bg-primary/10"
                                                : "text-muted-foreground hover:bg-muted"
                                )}
                            >
                                {status === "completed" ? (
                                    <CheckCircle2 className="h-4 w-4" />
                                ) : (
                                    <Icon className="h-4 w-4" />
                                )}
                                <span className="hidden sm:inline">{step.label}</span>
                            </Link>
                            {index < steps.length - 1 && (
                                <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                            )}
                        </React.Fragment>
                    )
                })}
            </div>
        )
    }

    // Full card version
    return (
        <Card className={className}>
            <CardHeader className="pb-4">
                <CardTitle className="text-lg">SpecKit Workflow</CardTitle>
                <CardDescription>
                    Guide specs through clarify, plan, checklist, tasks, analysis, and implementation
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid gap-4 md:grid-cols-4 xl:grid-cols-8">
                    {steps.map((step, index) => {
                        const status = stepStatus[step.key]
                        const isActive = currentStep === step.key
                        const isNextStep =
                            !currentStep &&
                            index === 0 &&
                            !status

                        return (
                            <div key={step.key} className="relative">
                                {/* Connector line */}
                                {index < steps.length - 1 && (
                                    <div className="hidden md:block absolute top-8 left-[calc(100%_-_8px)] w-[calc(100%_-_16px)] h-0.5 bg-muted">
                                        <div
                                            className={cn(
                                                "h-full transition-all",
                                                status === "completed" ? "bg-green-500 w-full" : "w-0"
                                            )}
                                        />
                                    </div>
                                )}

                                <Link href={getStepHref(step.key, projectId)}>
                                    <div
                                        className={cn(
                                            "border-2 rounded-lg p-4 transition-all hover:shadow-md cursor-pointer",
                                            getStatusColor(status, isActive)
                                        )}
                                    >
                                        <div className="flex items-center gap-3 mb-2">
                                            {getStatusIcon(status, isActive)}
                                            <span className="font-medium">{step.label}</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground mb-3">
                                            {step.description}
                                        </p>

                                        {/* Status badge */}
                                        <Badge
                                            variant={
                                                status === "completed"
                                                    ? "default"
                                                    : status === "in-progress"
                                                        ? "secondary"
                                                        : "outline"
                                            }
                                            className={cn(
                                                "text-xs",
                                                status === "completed" && "bg-green-500"
                                            )}
                                        >
                                            {status === "completed"
                                                ? "Complete"
                                                : status === "in-progress"
                                                    ? "In Progress"
                                                    : isActive
                                                        ? "Current"
                                                        : "Pending"}
                                        </Badge>
                                    </div>
                                </Link>

                                {/* Action button for next step */}
                                {showActions && isNextStep && (
                                    <Button size="sm" className="w-full mt-2" asChild>
                                        <Link href={getStepHref(step.key, projectId)}>
                                            Start
                                            <ArrowRight className="ml-2 h-4 w-4" />
                                        </Link>
                                    </Button>
                                )}
                            </div>
                        )
                    })}
                </div>
            </CardContent>
        </Card>
    )
}

/**
 * Inline workflow status indicator for spec cards
 */
export function SpecWorkflowBadges({
    hasSpec,
    hasPlan,
    hasTasks,
    inSprint,
}: {
    hasSpec?: boolean
    hasPlan?: boolean
    hasTasks?: boolean
    inSprint?: boolean
}) {
    return (
        <div className="flex items-center gap-1">
            {hasSpec && (
                <Badge variant="outline" className="text-xs gap-1">
                    <FileText className="h-3 w-3" />
                    Spec
                </Badge>
            )}
            {hasPlan && (
                <Badge variant="secondary" className="text-xs gap-1">
                    <ClipboardList className="h-3 w-3" />
                    Plan
                </Badge>
            )}
            {hasTasks && (
                <Badge className="text-xs gap-1 bg-blue-500">
                    <ListTodo className="h-3 w-3" />
                    Tasks
                </Badge>
            )}
            {inSprint && (
                <Badge className="text-xs gap-1 bg-purple-500">
                    <Kanban className="h-3 w-3" />
                    Execution
                </Badge>
            )}
        </div>
    )
}
