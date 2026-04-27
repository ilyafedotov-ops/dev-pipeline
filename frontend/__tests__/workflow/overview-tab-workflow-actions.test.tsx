import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OverviewTab } from "@/app/projects/[id]/components/overview-tab";

vi.mock("@/lib/api", () => ({
  useProject: () => ({
    data: {
      id: 12,
      name: "Demo Project",
      local_path: "/tmp/demo-project",
      policy_pack_key: null,
    },
    isLoading: false,
  }),
  useOnboarding: () => ({
    data: {
      status: "completed",
      blocking_clarifications: 0,
    },
    isLoading: false,
  }),
  useProjectProtocols: () => ({
    data: [],
  }),
  useSpecKitStatus: () => ({
    data: {
      initialized: true,
      spec_count: 1,
      specs: [
        {
          id: 77,
          name: "001-auth-flow",
          path: "specs/001-auth-flow",
          spec_path: "specs/001-auth-flow/spec.md",
          plan_path: "specs/001-auth-flow/plan.md",
          tasks_path: "specs/001-auth-flow/tasks.md",
          checklist_path: "specs/001-auth-flow/checklist.md",
          analysis_path: "specs/001-auth-flow/analysis.md",
          implement_path: "specs/001-auth-flow/_runtime",
          has_spec: true,
          has_plan: true,
          has_tasks: true,
          status: "completed",
        },
      ],
    },
  }),
  usePolicyFindings: () => ({
    data: [],
  }),
  useProjectCommits: () => ({
    data: [],
  }),
  useProjectPulls: () => ({
    data: [],
  }),
  useClarifySpec: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useGenerateChecklist: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useAnalyzeSpec: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useRunImplement: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useCreateProtocol: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

describe("OverviewTab workflow actions", () => {
  it("promotes the canonical workflow and routes workflow steps through the spec workspace", () => {
    render(<OverviewTab projectId={12} />);

    expect(screen.getByRole("link", { name: /open execution/i }).getAttribute("href")).toBe(
      "/projects/12?tab=execution"
    );
    expect(screen.getByRole("link", { name: /specification/i }).getAttribute("href")).toBe(
      "/projects/12?wizard=generate-specs&tab=spec"
    );
    expect(screen.getByRole("link", { name: /implementation plan/i }).getAttribute("href")).toBe(
      "/projects/12?tab=spec&step=plan"
    );
    expect(screen.getByRole("link", { name: /task list/i }).getAttribute("href")).toBe(
      "/projects/12?tab=spec&step=tasks"
    );
    expect(screen.getByRole("link", { name: /analyze/i }).getAttribute("href")).toBe(
      "/projects/12?tab=spec&step=analyze"
    );
  });
});
