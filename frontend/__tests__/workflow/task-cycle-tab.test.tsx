import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TaskCycleTab } from "@/app/projects/[id]/components/task-cycle-tab";

const startBrownfieldRunMock = vi.fn();

vi.mock("@/lib/api", () => ({
  useProjectProtocols: () => ({
    data: [{ id: 41, protocol_name: "brownfield-auth", status: "planned" }],
    isLoading: false,
  }),
  useProjectTaskCycle: () => ({
    data: [],
    isLoading: false,
  }),
  useSprints: () => ({
    data: [],
  }),
  useStartBrownfieldRun: () => ({
    mutateAsync: startBrownfieldRunMock,
    isPending: false,
  }),
  useBuildContextWorkItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useImplementWorkItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useReviewWorkItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useQaWorkItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMarkPrReady: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("TaskCycleTab", () => {
  beforeEach(() => {
    startBrownfieldRunMock.mockReset();
  });

  it("renders the task-cycle starter workflow", () => {
    render(<TaskCycleTab projectId={9} />);

    expect(screen.getByRole("heading", { name: /task cycle/i })).toBeTruthy();
    expect(screen.getByPlaceholderText(/describe the brownfield change/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /start brownfield run/i })).toBeTruthy();
  });

  it("starts a brownfield run from the tab", async () => {
    startBrownfieldRunMock.mockResolvedValue({
      success: true,
      output_mode: "task_cycle",
      protocol: { id: 41, protocol_name: "brownfield-auth" },
      task_ids: [],
      work_items: [],
      warnings: [],
    });

    render(<TaskCycleTab projectId={9} />);

    fireEvent.change(screen.getByPlaceholderText(/feature name/i), {
      target: { value: "Auth hardening" },
    });
    fireEvent.change(screen.getByPlaceholderText(/describe the brownfield change/i), {
      target: { value: "Tighten the auth review flow for existing users." },
    });
    fireEvent.click(screen.getByRole("button", { name: /start brownfield run/i }));

    await waitFor(() => {
      expect(startBrownfieldRunMock).toHaveBeenCalledWith({
        projectId: 9,
        data: {
          feature_name: "Auth hardening",
          feature_request: "Tighten the auth review flow for existing users.",
          output_mode: "task_cycle",
          sprint_id: undefined,
          sprint_name: undefined,
        },
      });
    });
  });
});
