import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TaskCycleTab } from "@/app/projects/[id]/components/task-cycle-tab";

const startBrownfieldRunMock = vi.fn();
const buildContextMock = vi.fn();
const implementMock = vi.fn();
const reviewMock = vi.fn();
const qaMock = vi.fn();
const markPrReadyMock = vi.fn();

let workItemsData: unknown[] = [];
let artifactContentData: {
  isLoading: boolean;
  error: Error | null;
  data: { id: string; name: string; type: string; content: string; truncated: boolean } | null;
} = {
  isLoading: false,
  error: null,
  data: null,
};

vi.mock("@/lib/api", () => ({
  useProjectProtocols: () => ({
    data: [{ id: 41, protocol_name: "brownfield-auth", status: "planned" }],
    isLoading: false,
  }),
  useProjectTaskCycle: () => ({
    data: workItemsData,
    isLoading: false,
  }),
  useSprints: () => ({
    data: [],
  }),
  useStartBrownfieldRun: () => ({
    mutateAsync: startBrownfieldRunMock,
    isPending: false,
  }),
  useBuildContextWorkItem: () => ({ mutateAsync: buildContextMock, isPending: false }),
  useImplementWorkItem: () => ({ mutateAsync: implementMock, isPending: false }),
  useReviewWorkItem: () => ({ mutateAsync: reviewMock, isPending: false }),
  useQaWorkItem: () => ({ mutateAsync: qaMock, isPending: false }),
  useMarkPrReady: () => ({ mutateAsync: markPrReadyMock, isPending: false }),
  useWorkItemArtifactContent: () => artifactContentData,
}));

describe("TaskCycleTab", () => {
  beforeEach(() => {
    startBrownfieldRunMock.mockReset();
    buildContextMock.mockReset();
    implementMock.mockReset();
    reviewMock.mockReset();
    qaMock.mockReset();
    markPrReadyMock.mockReset();
    workItemsData = [];
    artifactContentData = {
      isLoading: false,
      error: null,
      data: null,
    };
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

  it("renders helper agents, task dir, and artifact preview actions", async () => {
    workItemsData = [
      {
        id: 52,
        project_id: 9,
        protocol_run_id: 41,
        title: "step-01-phase-1-setup",
        status: "context_ready",
        context_status: "needs_clarification",
      review_status: "pending",
      qa_status: "pending",
      owner_agent: "codex",
      helper_agents: ["trace", "tests"],
      helper_agent_summary: "2 helpers configured under the owner: trace, tests (internal delegation only)",
      task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/41/work-items/52",
        artifact_refs: {
          task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/41/work-items/52",
          context_pack_json: "/tmp/context_pack.json",
          context_pack_md: "/tmp/context_pack.md",
          review_input_json: "/tmp/review_input.json",
          review_input_md: "/tmp/review_input.md",
          review_report_json: "/tmp/review_report.json",
          review_report_md: "/tmp/review_report.md",
          test_report_json: "/tmp/test_report.json",
          test_report_md: "/tmp/test_report.md",
          rework_pack_json: "/tmp/rework_pack.json",
          step_artifacts_dir: "/tmp/step-artifacts",
        },
        artifact_availability: {
          context_pack_md: true,
          review_report_md: true,
          test_report_md: true,
          rework_pack_json: false,
        },
        depends_on: [],
        pr_ready: false,
        blocking_clarifications: 2,
        blocking_policy_findings: 1,
        iteration_count: 1,
        max_iterations: 5,
        summary: "Waiting for repo entry points",
      },
    ];
    artifactContentData = {
      isLoading: false,
      error: null,
      data: {
        id: "context_pack_md",
        name: "context_pack.md",
        type: "text",
        content: "# Context Pack\n\nhello",
        truncated: false,
      },
    };

    render(<TaskCycleTab projectId={9} />);

    expect(screen.getByText(/helpers: trace, tests/i)).toBeTruthy();
    expect(screen.getAllByText(/pr ready: no/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/internal delegation only/i)).toBeTruthy();
    expect(screen.getByText(/helper activity:/i)).toBeTruthy();
    expect(screen.getByText(/implementation is blocked until context is ready/i)).toBeTruthy();
    expect(screen.getByText(/next: resolve context and blocking clarifications/i)).toBeTruthy();
    expect(screen.getByText("/tmp/repo/.devgodzilla/task-cycle/protocols/41/work-items/52")).toBeTruthy();
    expect(screen.getByRole("button", { name: /^implement$/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.getByRole("button", { name: /^review$/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.getByRole("button", { name: /^qa$/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.getByRole("button", { name: /mark pr ready/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.getByRole("button", { name: /view rework/i }).getAttribute("disabled")).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /view context/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /context pack/i })).toBeTruthy();
      expect(screen.getByText(/hello/i)).toBeTruthy();
    });
  });

  it("disables artifact actions when the artifact is unavailable", () => {
    workItemsData = [
      {
        id: 77,
        project_id: 9,
        protocol_run_id: 41,
        title: "step-02-phase-2-core-implementation",
        status: "awaiting_review",
        context_status: "ready",
        review_status: "passed",
        qa_status: "pending",
        owner_agent: "codex",
        helper_agents: [],
        helper_agent_summary: null,
        task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/41/work-items/77",
        artifact_refs: {
          task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/41/work-items/77",
          context_pack_json: "/tmp/context_pack.json",
          context_pack_md: "/tmp/context_pack.md",
          review_input_json: "/tmp/review_input.json",
          review_input_md: "/tmp/review_input.md",
          review_report_json: "/tmp/review_report.json",
          review_report_md: "/tmp/review_report.md",
          test_report_json: "/tmp/test_report.json",
          test_report_md: "/tmp/test_report.md",
          rework_pack_json: "/tmp/rework_pack.json",
          step_artifacts_dir: "/tmp/step-artifacts",
        },
        artifact_availability: {
          context_pack_md: true,
          review_report_md: true,
          test_report_md: false,
          rework_pack_json: false,
        },
        depends_on: [],
        pr_ready: false,
        blocking_clarifications: 0,
        blocking_policy_findings: 0,
        iteration_count: 0,
        max_iterations: 5,
        summary: null,
      },
    ];

    render(<TaskCycleTab projectId={9} />);

    expect(screen.getByText(/helpers: none/i)).toBeTruthy();
    expect(screen.getByText(/helper activity: no helper subtasks configured under the owner/i)).toBeTruthy();
    expect(screen.getAllByText(/pr ready: no/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /view qa/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.getByRole("button", { name: /view rework/i }).getAttribute("disabled")).not.toBeNull();
  });
});
