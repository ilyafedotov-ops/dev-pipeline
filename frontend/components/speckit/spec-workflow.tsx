"use client";

import * as React from "react";
import Link from "next/link";

import {
  ArrowRight,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  ClipboardList,
  FileSearch,
  FileText,
  Kanban,
  ListTodo,
  Loader2,
  MessageSquare,
  Play,
  PlayCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getProjectExecutionPath,
  getProjectSpecWorkflowPath,
  getProjectSpecWorkspacePath,
  getProjectSpecWorkspaceStepPath,
} from "@/lib/project-routes";
import { cn } from "@/lib/utils";

export type WorkflowStep =
  | "spec"
  | "clarify"
  | "plan"
  | "checklist"
  | "tasks"
  | "analyze"
  | "implement"
  | "sprint";
export type StepStatus = "pending" | "in-progress" | "completed";

interface SpecWorkflowProps {
  projectId: number;
  currentStep?: WorkflowStep;
  /** Status for each step */
  stepStatus?: {
    spec?: StepStatus;
    clarify?: StepStatus;
    plan?: StepStatus;
    checklist?: StepStatus;
    tasks?: StepStatus;
    analyze?: StepStatus;
    implement?: StepStatus;
    sprint?: StepStatus;
  };
  /** Show action buttons for next steps */
  showActions?: boolean;
  /** Compact mode for inline display */
  compact?: boolean;
  className?: string;
}

const steps: { key: WorkflowStep; label: string; icon: React.ElementType; description: string }[] =
  [
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
  ];

function getStepHref(step: WorkflowStep, projectId: number): string {
  switch (step) {
    case "spec":
      return getProjectSpecWorkflowPath(projectId);
    case "clarify":
    case "plan":
    case "checklist":
    case "tasks":
    case "analyze":
    case "implement":
      return getProjectSpecWorkspaceStepPath(projectId, step);
    case "sprint":
      return getProjectExecutionPath(projectId);
    default:
      return getProjectSpecWorkspacePath(projectId);
  }
}

function getStatusIcon(status: StepStatus | undefined, isActive: boolean) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "in-progress":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    default:
      return isActive ? (
        <div className="bg-primary flex h-5 w-5 items-center justify-center rounded-full">
          <Play className="text-primary-foreground h-3 w-3" />
        </div>
      ) : (
        <Circle className="text-muted-foreground h-5 w-5" />
      );
  }
}

function getStatusColor(status: StepStatus | undefined, isActive: boolean): string {
  if (status === "completed") return "border-green-500 bg-green-500/10";
  if (status === "in-progress") return "border-blue-500 bg-blue-500/10";
  if (isActive) return "border-primary bg-primary/10";
  return "border-muted";
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
          const status = stepStatus[step.key];
          const isActive = currentStep === step.key;
          const Icon = step.icon;

          return (
            <React.Fragment key={step.key}>
              <Link
                href={getStepHref(step.key, projectId)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2 py-1 text-sm transition-colors",
                  status === "completed"
                    ? "text-green-600 hover:bg-green-500/10"
                    : status === "in-progress"
                      ? "text-blue-600 hover:bg-blue-500/10"
                      : isActive
                        ? "text-primary hover:bg-primary/10 font-medium"
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
                <ArrowRight className="text-muted-foreground h-3 w-3 flex-shrink-0" />
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
  }

  // Full card version
  return (
    <Card className={className}>
      <CardHeader className="pb-4">
        <CardTitle className="text-lg">SpecKit Workflow</CardTitle>
        <CardDescription>
          Default happy path starts in the full spec workflow, then continues in the spec workspace
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {steps.map((step, index) => {
            const status = stepStatus[step.key];
            const isActive = currentStep === step.key;
            const isNextStep = !currentStep && index === 0 && !status;

            return (
              <div key={step.key} className="relative w-[180px] flex-shrink-0">
                {/* Connector line */}
                {index < steps.length - 1 && (
                  <div className="bg-muted pointer-events-none absolute top-7 left-full hidden h-0.5 w-4 z-0 sm:block">
                    <div
                      className={cn(
                        "h-full transition-all",
                        status === "completed" ? "w-full bg-green-500" : "w-0"
                      )}
                    />
                  </div>
                )}

                <Link href={getStepHref(step.key, projectId)}>
                  <div
                    className={cn(
                      "relative z-10 cursor-pointer rounded-lg border-2 p-4 transition-all hover:shadow-md",
                      getStatusColor(status, isActive)
                    )}
                  >
                    <div className="mb-2 flex min-w-0 items-center gap-3">
                      <div className="flex-shrink-0">{getStatusIcon(status, isActive)}</div>
                      <span className="min-w-0 flex-1 text-sm leading-tight font-medium whitespace-normal">
                        {step.label}
                      </span>
                    </div>
                    <p className="text-muted-foreground mb-3 text-xs">{step.description}</p>

                    {/* Status badge */}
                    <Badge
                      variant={
                        status === "completed"
                          ? "default"
                          : status === "in-progress"
                            ? "secondary"
                            : "outline"
                      }
                      className={cn("text-xs", status === "completed" && "bg-green-500")}
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
                  <Button size="sm" className="mt-2 w-full" asChild>
                    <Link href={getStepHref(step.key, projectId)}>
                      Start
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
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
  hasSpec?: boolean;
  hasPlan?: boolean;
  hasTasks?: boolean;
  inSprint?: boolean;
}) {
  return (
    <div className="flex items-center gap-1">
      {hasSpec && (
        <Badge variant="outline" className="gap-1 text-xs">
          <FileText className="h-3 w-3" />
          Spec
        </Badge>
      )}
      {hasPlan && (
        <Badge variant="secondary" className="gap-1 text-xs">
          <ClipboardList className="h-3 w-3" />
          Plan
        </Badge>
      )}
      {hasTasks && (
        <Badge className="gap-1 bg-blue-500 text-xs">
          <ListTodo className="h-3 w-3" />
          Tasks
        </Badge>
      )}
      {inSprint && (
        <Badge className="gap-1 bg-purple-500 text-xs">
          <Kanban className="h-3 w-3" />
          Execution
        </Badge>
      )}
    </div>
  );
}
