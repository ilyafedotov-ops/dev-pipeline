import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SpecTab } from "@/app/projects/[id]/components/spec-tab";

const initMutateAsyncMock = vi.fn();
const refetchStatusMock = vi.fn();
const refetchSpecsMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  useProject: () => ({
    data: { id: 9, name: "Demo Project" },
    isLoading: false,
  }),
  useSpecKitStatus: () => ({
    data: { initialized: false, spec_count: 0, specs: [] },
    isLoading: false,
    refetch: refetchStatusMock,
  }),
  useSpecifications: () => ({
    data: [],
    isLoading: false,
    refetch: refetchSpecsMock,
  }),
  useSpecificationContent: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
  useInitSpecKit: () => ({
    mutateAsync: initMutateAsyncMock,
    isPending: false,
  }),
  useClarifySpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDetectAmbiguities: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    data: null,
  }),
  useGenerateChecklist: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAnalyzeSpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGeneratePlan: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateTasks: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRunImplement: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateSpec: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStopSpecRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteSpecRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("SpecTab uninitialized state", () => {
  beforeEach(() => {
    initMutateAsyncMock.mockReset();
    refetchStatusMock.mockReset();
    refetchSpecsMock.mockReset();
    pushMock.mockReset();
  });

  it("offers an initialize action instead of only CLI instructions", () => {
    render(<SpecTab projectId={9} />);

    expect(screen.getByRole("button", { name: /initialize speckit/i })).toBeTruthy();
  });

  it("initializes SpecKit from the project spec tab", async () => {
    initMutateAsyncMock.mockResolvedValue({ success: true });

    render(<SpecTab projectId={9} />);

    fireEvent.click(screen.getByRole("button", { name: /initialize speckit/i }));

    expect(initMutateAsyncMock).toHaveBeenCalledWith({ project_id: 9 });
  });
});
