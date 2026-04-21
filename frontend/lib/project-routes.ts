export function getProjectExecutionPath(
  projectId: number | string,
  sprintId?: number | string | null
): string {
  const params = new URLSearchParams({ tab: "execution" });
  if (sprintId !== undefined && sprintId !== null && sprintId !== "") {
    params.set("sprint", String(sprintId));
  }
  return `/projects/${projectId}?${params.toString()}`;
}

export function getProjectSpecWorkspacePath(projectId: number | string): string {
  return `/projects/${projectId}?tab=spec`;
}

export type SpecWorkspaceStep =
  | "spec"
  | "clarify"
  | "plan"
  | "checklist"
  | "tasks"
  | "analyze"
  | "implement";

export function getProjectSpecWorkspaceStepPath(
  projectId: number | string,
  step: SpecWorkspaceStep
): string {
  const params = new URLSearchParams({ tab: "spec", step });
  return `/projects/${projectId}?${params.toString()}`;
}

export function getProjectSpecWorkflowPath(projectId: number | string): string {
  const params = new URLSearchParams({
    wizard: "generate-specs",
    tab: "spec",
  });
  return `/projects/${projectId}?${params.toString()}`;
}

export function getProjectManualPlanWizardPath(projectId: number | string): string {
  return `/projects/${projectId}?wizard=design-solution`;
}

export function getProjectManualTasksWizardPath(projectId: number | string): string {
  return `/projects/${projectId}?wizard=implement-feature`;
}

export type SpecificationDetailTab =
  | "overview"
  | "tasks"
  | "spec_file"
  | "plan_file"
  | "tasks_file"
  | "checklist"
  | "analysis"
  | "protocol";

export function getSpecificationDetailPath(
  specId: number | string,
  tab?: SpecificationDetailTab
): string {
  const basePath = `/specifications/${specId}`;
  if (!tab) {
    return basePath;
  }
  const params = new URLSearchParams({ tab });
  return `${basePath}?${params.toString()}`;
}

export function getSpecificationReviewPath(specId: number | string): string {
  return getSpecificationDetailPath(specId, "analysis");
}
