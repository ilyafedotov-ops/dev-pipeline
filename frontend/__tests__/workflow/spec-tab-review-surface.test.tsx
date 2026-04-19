import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SpecTab } from "@/app/projects/[id]/components/spec-tab";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api", () => ({
  useProject: () => ({
    data: { id: 11, name: "Spec Review Project" },
    isLoading: false,
  }),
  useSpecKitStatus: () => ({
    data: {
      initialized: true,
      constitution_hash: "abc123",
      constitution_version: "1.0.0",
      spec_count: 1,
      specs: [
        {
          name: "review-ready",
          path: "specs/0001-review-ready",
          spec_path: "specs/0001-review-ready/spec.md",
          plan_path: "specs/0001-review-ready/plan.md",
          tasks_path: "specs/0001-review-ready/tasks.md",
          checklist_path: "specs/0001-review-ready/checklist.md",
          analysis_path: "specs/0001-review-ready/analysis.md",
          implement_path: "specs/0001-review-ready/_runtime",
          has_spec: true,
          has_plan: true,
          has_tasks: true,
          status: "completed",
          spec_run_id: 77,
        },
      ],
    },
    isLoading: false,
    refetch: vi.fn(),
  }),
  useSpecifications: () => ({
    data: [
      {
        id: 77,
        title: "Review Ready",
        path: "specs/0001-review-ready",
        spec_path: "specs/0001-review-ready/spec.md",
        plan_path: "specs/0001-review-ready/plan.md",
        tasks_path: "specs/0001-review-ready/tasks.md",
        checklist_path: "specs/0001-review-ready/checklist.md",
        analysis_path: "specs/0001-review-ready/analysis.md",
        implement_path: "specs/0001-review-ready/_runtime",
        has_plan: true,
        has_tasks: true,
        linked_tasks: 5,
        completed_tasks: 2,
        protocol_id: 42,
        status: "completed",
      },
    ],
    isLoading: false,
    refetch: vi.fn(),
  }),
  useInitSpecKit: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useClarifySpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateChecklist: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAnalyzeSpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRunImplement: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateSpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGeneratePlan: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateTasks: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRunWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("SpecTab review surface", () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  it("shows review readiness and protocol linkage for implementation-ready specs", () => {
    const { container } = render(<SpecTab projectId={11} />);

    expect(screen.getByRole("link", { name: /run spec workflow/i }).getAttribute("href")).toBe(
      "/projects/11?wizard=generate-specs&tab=spec"
    );
    expect(
      screen.getByRole("link", { name: /review implementation/i }).getAttribute("href")
    ).toBe("/specifications/77?tab=analysis");
    expect(screen.getAllByText(/review ready/i).length).toBeGreaterThan(0);
    expect(container.textContent).toContain("Analysis: Ready");
    expect(container.textContent).toContain("Checklist: Ready");
    const protocolLink = screen.getByRole("link", { name: /view protocol #42/i });
    expect(protocolLink.getAttribute("href")).toBe("/protocols/42");
  });
});
