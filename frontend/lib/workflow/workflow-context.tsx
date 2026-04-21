"use client";

import * as React from "react";

import {
  getStepHref,
  inferCompletedSteps,
  inferStepStatus,
  WORKFLOW_STEP_ORDER,
  WORKFLOW_STEPS,
  WorkflowStep,
  WorkflowStepStatus,
} from "./types";

interface WorkflowState {
  projectId: number;
  currentStep: WorkflowStep;
  stepStatus: Record<WorkflowStep, WorkflowStepStatus>;
  completedSteps: Set<WorkflowStep>;
}

interface WorkflowContextValue extends WorkflowState {
  setCurrentStep: (step: WorkflowStep) => void;
  markStepComplete: (step: WorkflowStep) => void;
  markStepFailed: (step: WorkflowStep) => void;
  getStepStatus: (step: WorkflowStep) => WorkflowStepStatus;
  getStepHref: (step: WorkflowStep) => string;
  isStepAccessible: (step: WorkflowStep) => boolean;
  getNextStep: () => WorkflowStep | null;
  refreshFromSpecData: (data: {
    hasSpec?: boolean;
    hasPlan?: boolean;
    hasTasks?: boolean;
    hasChecklist?: boolean;
    hasAnalysis?: boolean;
    hasImplement?: boolean;
    inSprint?: boolean;
  }) => void;
  reset: () => void;
}

const WorkflowContext = React.createContext<WorkflowContextValue | null>(null);

export interface WorkflowProviderProps {
  projectId: number;
  children: React.ReactNode;
  initialStep?: WorkflowStep;
  specData?: {
    hasSpec?: boolean;
    hasPlan?: boolean;
    hasTasks?: boolean;
    hasChecklist?: boolean;
    hasAnalysis?: boolean;
    hasImplement?: boolean;
    inSprint?: boolean;
  };
}

export function WorkflowProvider({
  projectId,
  children,
  initialStep = "spec",
  specData,
}: WorkflowProviderProps) {
  const [currentStep, setCurrentStep] = React.useState<WorkflowStep>(initialStep);
  const [completedSteps, setCompletedSteps] = React.useState<Set<WorkflowStep>>(() => {
    if (specData) {
      return inferCompletedSteps(specData);
    }
    return new Set();
  });

  const stepStatus = React.useMemo<Record<WorkflowStep, WorkflowStepStatus>>(() => {
    const status: Record<WorkflowStep, WorkflowStepStatus> = {} as Record<
      WorkflowStep,
      WorkflowStepStatus
    >;

    for (const step of WORKFLOW_STEP_ORDER) {
      status[step] = inferStepStatus(step, {
        hasSpec: completedSteps.has("spec"),
        hasPlan: completedSteps.has("plan"),
        hasTasks: completedSteps.has("tasks"),
        hasChecklist: completedSteps.has("checklist"),
        hasAnalysis: completedSteps.has("analyze"),
        hasImplement: completedSteps.has("implement"),
        inSprint: completedSteps.has("sprint"),
      });
    }

    if (currentStep && status[currentStep] === "pending") {
      status[currentStep] = "in-progress";
    }

    return status;
  }, [completedSteps, currentStep]);

  const getStepStatus = React.useCallback(
    (step: WorkflowStep): WorkflowStepStatus => {
      return stepStatus[step] || "pending";
    },
    [stepStatus]
  );

  const getStepHrefForProject = React.useCallback(
    (step: WorkflowStep): string => {
      return getStepHref(step, projectId);
    },
    [projectId]
  );

  const isStepAccessible = React.useCallback(
    (step: WorkflowStep): boolean => {
      const config = WORKFLOW_STEPS[step];
      if (!config.requiredSteps) return true;
      return config.requiredSteps.every((required) => completedSteps.has(required));
    },
    [completedSteps]
  );

  const getNextStep = React.useCallback((): WorkflowStep | null => {
    const currentIndex = WORKFLOW_STEP_ORDER.indexOf(currentStep);

    for (let i = currentIndex + 1; i < WORKFLOW_STEP_ORDER.length; i++) {
      const nextStep = WORKFLOW_STEP_ORDER[i];
      if (isStepAccessible(nextStep)) {
        return nextStep;
      }
    }

    return null;
  }, [currentStep, isStepAccessible]);

  const markStepComplete = React.useCallback((step: WorkflowStep) => {
    setCompletedSteps((prev) => new Set([...prev, step]));
  }, []);

  const markStepFailed = React.useCallback((step: WorkflowStep) => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.delete(step);
      return next;
    });
  }, []);

  const refreshFromSpecData = React.useCallback(
    (data: {
      hasSpec?: boolean;
      hasPlan?: boolean;
      hasTasks?: boolean;
      hasChecklist?: boolean;
      hasAnalysis?: boolean;
      hasImplement?: boolean;
      inSprint?: boolean;
    }) => {
      setCompletedSteps(inferCompletedSteps(data));
    },
    []
  );

  const reset = React.useCallback(() => {
    setCurrentStep("spec");
    setCompletedSteps(new Set());
  }, []);

  const value: WorkflowContextValue = React.useMemo(
    () => ({
      projectId,
      currentStep,
      stepStatus,
      completedSteps,
      setCurrentStep,
      markStepComplete,
      markStepFailed,
      getStepStatus,
      getStepHref: getStepHrefForProject,
      isStepAccessible,
      getNextStep,
      refreshFromSpecData,
      reset,
    }),
    [
      projectId,
      currentStep,
      stepStatus,
      completedSteps,
      markStepComplete,
      markStepFailed,
      getStepStatus,
      getStepHrefForProject,
      isStepAccessible,
      getNextStep,
      refreshFromSpecData,
      reset,
    ]
  );

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow(): WorkflowContextValue {
  const context = React.useContext(WorkflowContext);
  if (!context) {
    throw new Error("useWorkflow must be used within a WorkflowProvider");
  }
  return context;
}

export function useOptionalWorkflow(): WorkflowContextValue | null {
  return React.useContext(WorkflowContext);
}
