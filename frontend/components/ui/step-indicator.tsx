"use client";

import * as React from "react";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export interface StepItem {
  id: string;
  label: string;
  description?: string;
  icon?: React.ElementType;
}

export type StepItemStatus = "pending" | "active" | "completed" | "error" | "loading";

export interface StepIndicatorProps {
  steps: StepItem[];
  currentStep: string;
  completedSteps?: Set<string>;
  stepStatus?: Record<string, StepItemStatus>;
  onStepClick?: (stepId: string) => void;
  variant?: "horizontal" | "vertical" | "compact";
  showLabels?: boolean;
  showConnectors?: boolean;
  className?: string;
}

const getStatusClasses = (status: StepItemStatus): string => {
  switch (status) {
    case "completed":
      return "bg-green-500 text-white border-green-500";
    case "active":
      return "bg-primary text-primary-foreground border-primary";
    case "loading":
      return "bg-blue-500 text-white border-blue-500";
    case "error":
      return "bg-destructive text-destructive-foreground border-destructive";
    default:
      return "bg-muted text-muted-foreground border-muted";
  }
};

const getStatusIcon = (status: StepItemStatus, stepNumber: number, Icon?: React.ElementType) => {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5" />;
    case "loading":
      return <Loader2 className="h-5 w-5 animate-spin" />;
    default:
      return Icon ? (
        <Icon className="h-5 w-5" />
      ) : (
        <span className="text-sm font-medium">{stepNumber}</span>
      );
  }
};

export function StepIndicator({
  steps,
  currentStep,
  completedSteps = new Set(),
  stepStatus,
  onStepClick,
  variant = "horizontal",
  showLabels = true,
  showConnectors = true,
  className,
}: StepIndicatorProps) {
  const getStepStatus = (stepId: string): StepItemStatus => {
    if (stepStatus?.[stepId]) return stepStatus[stepId];
    if (completedSteps.has(stepId)) return "completed";
    if (currentStep === stepId) return "active";
    return "pending";
  };

  const stepIndex = steps.findIndex((s) => s.id === currentStep);

  // Keyboard navigation handler
  const handleKeyDown = React.useCallback(
    (event: React.KeyboardEvent, stepId: string) => {
      if (!onStepClick) return;

      const currentIndex = steps.findIndex((s) => s.id === stepId);
      let targetIndex: number | null = null;

      switch (event.key) {
        case "ArrowRight":
        case "ArrowDown":
          targetIndex = Math.min(currentIndex + 1, steps.length - 1);
          break;
        case "ArrowLeft":
        case "ArrowUp":
          targetIndex = Math.max(currentIndex - 1, 0);
          break;
        case "Home":
          targetIndex = 0;
          break;
        case "End":
          targetIndex = steps.length - 1;
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          onStepClick(stepId);
          return;
      }

      if (targetIndex !== null) {
        event.preventDefault();
        const targetStep = steps[targetIndex];
        const targetStatus = getStepStatus(targetStep.id);
        const isTargetClickable = targetStatus === "completed" || targetIndex <= stepIndex + 1;
        if (isTargetClickable) {
          onStepClick(targetStep.id);
        }
      }
    },
    [onStepClick, steps, stepIndex]
  );

  if (variant === "compact") {
    return (
      <nav
        className={cn("flex items-center gap-2", className)}
        role="navigation"
        aria-label="Progress steps"
      >
        <ol className="flex items-center gap-2">
          {steps.map((step, index) => {
            const status = getStepStatus(step.id);
            const Icon = step.icon;
            const isClickable = onStepClick && (status === "completed" || index <= stepIndex + 1);

            return (
              <li key={step.id} className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={!isClickable}
                  onClick={() => onStepClick?.(step.id)}
                  onKeyDown={(e) => handleKeyDown(e, step.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2 py-1 text-sm transition-colors",
                    status === "completed" && "text-green-600 hover:bg-green-500/10",
                    status === "active" && "text-primary hover:bg-primary/10 font-medium",
                    status === "loading" && "text-blue-600 hover:bg-blue-500/10",
                    status === "error" && "text-destructive hover:bg-destructive/10",
                    status === "pending" && "text-muted-foreground hover:bg-muted",
                    isClickable && "cursor-pointer",
                    !isClickable && "cursor-default"
                  )}
                  aria-current={status === "active" ? "step" : undefined}
                  aria-label={`${step.label}${status === "completed" ? ", completed" : status === "active" ? ", current" : ""}`}
                >
                  {status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  ) : Icon ? (
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Circle className="h-4 w-4" aria-hidden="true" />
                  )}
                  {showLabels && <span className="hidden sm:inline">{step.label}</span>}
                </button>
                {showConnectors && index < steps.length - 1 && (
                  <div className="bg-muted h-0.5 w-4 flex-shrink-0" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    );
  }

  if (variant === "vertical") {
    return (
      <nav
        className={cn("flex flex-col gap-4", className)}
        role="navigation"
        aria-label="Progress steps"
      >
        <ol className="flex flex-col gap-4">
          {steps.map((step, index) => {
            const status = getStepStatus(step.id);
            const Icon = step.icon;
            const isClickable = onStepClick && (status === "completed" || index <= stepIndex + 1);

            return (
              <li key={step.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <button
                    type="button"
                    disabled={!isClickable}
                    onClick={() => onStepClick?.(step.id)}
                    onKeyDown={(e) => handleKeyDown(e, step.id)}
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                      getStatusClasses(status),
                      isClickable && "cursor-pointer hover:opacity-80",
                      !isClickable && "cursor-default"
                    )}
                    aria-current={status === "active" ? "step" : undefined}
                    aria-label={`${step.label}${status === "completed" ? ", completed" : status === "active" ? ", current" : ""}`}
                  >
                    {getStatusIcon(status, index + 1, Icon)}
                  </button>
                  {showConnectors && index < steps.length - 1 && (
                    <div
                      className={cn(
                        "my-2 w-0.5 flex-1",
                        completedSteps.has(step.id) ? "bg-green-500" : "bg-muted"
                      )}
                      aria-hidden="true"
                    />
                  )}
                </div>
                <div className="flex-1 pb-4">
                  {showLabels && (
                    <>
                      <p
                        className={cn(
                          "text-sm font-medium",
                          status === "active" && "text-primary",
                          status === "pending" && "text-muted-foreground"
                        )}
                      >
                        {step.label}
                      </p>
                      {step.description && (
                        <p className="text-muted-foreground text-xs">{step.description}</p>
                      )}
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </nav>
    );
  }

  // Horizontal (default)
  return (
    <nav
      className={cn("bg-muted/30 rounded-lg border p-4", className)}
      role="navigation"
      aria-label="Progress steps"
    >
      <ol className="flex items-center justify-between text-sm">
        {steps.map((step, index) => {
          const status = getStepStatus(step.id);
          const Icon = step.icon;
          const isClickable = onStepClick && (status === "completed" || index <= stepIndex + 1);

          return (
            <li key={step.id} className="flex items-center gap-3">
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => onStepClick?.(step.id)}
                onKeyDown={(e) => handleKeyDown(e, step.id)}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors",
                  getStatusClasses(status),
                  isClickable && "cursor-pointer hover:opacity-80",
                  !isClickable && "cursor-default"
                )}
                aria-current={status === "active" ? "step" : undefined}
                aria-label={`${step.label}${status === "completed" ? " (completed)" : status === "active" ? " (current)" : ""}`}
              >
                {getStatusIcon(status, index + 1, Icon)}
              </button>
              {showLabels && (
                <span className={cn(status === "active" ? "font-medium" : "text-muted-foreground")}>
                  {step.label}
                </span>
              )}
              {showConnectors && index < steps.length - 1 && (
                <div
                  className={cn(
                    "mx-2 h-0.5 flex-1",
                    completedSteps.has(step.id) ? "bg-green-500" : "bg-muted"
                  )}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function useStepNavigation(steps: StepItem[], initialStep?: string) {
  const [currentStep, setCurrentStep] = React.useState(initialStep ?? steps[0]?.id ?? "");
  const [completedSteps, setCompletedSteps] = React.useState<Set<string>>(new Set());

  const currentIndex = steps.findIndex((s) => s.id === currentStep);

  const goToNext = React.useCallback(() => {
    if (currentIndex < steps.length - 1) {
      setCompletedSteps((prev) => new Set([...prev, currentStep]));
      setCurrentStep(steps[currentIndex + 1].id);
    }
  }, [currentIndex, currentStep, steps]);

  const goToPrevious = React.useCallback(() => {
    if (currentIndex > 0) {
      setCurrentStep(steps[currentIndex - 1].id);
    }
  }, [currentIndex, steps]);

  const goToStep = React.useCallback(
    (stepId: string) => {
      const index = steps.findIndex((s) => s.id === stepId);
      if (index !== -1 && index <= currentIndex + 1) {
        setCurrentStep(stepId);
      }
    },
    [currentIndex, steps]
  );

  const isFirst = currentIndex === 0;
  const isLast = currentIndex === steps.length - 1;

  return {
    currentStep,
    setCurrentStep,
    completedSteps,
    setCompletedSteps,
    currentIndex,
    goToNext,
    goToPrevious,
    goToStep,
    isFirst,
    isLast,
    markComplete: (stepId: string) => setCompletedSteps((prev) => new Set([...prev, stepId])),
    reset: (step?: string) => {
      setCurrentStep(step ?? steps[0]?.id ?? "");
      setCompletedSteps(new Set());
    },
  };
}
