import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ArtifactsTab } from "@/app/protocols/[id]/components/artifacts-tab";

const getMock = vi.fn();

vi.mock("@/lib/api", () => ({
  useProtocolArtifacts: () => ({
    data: [
      {
        id: "92:quality-report.md",
        protocol_run_id: 35,
        step_run_id: 92,
        run_id: null,
        name: "quality-report.md",
        type: "report",
        kind: "report",
        size: 458,
        bytes: 458,
        created_at: "2026-04-22T07:58:25.779131+00:00",
      },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    getConfig: () => ({ baseUrl: "/api/v1" }),
  },
}));

describe("Protocol artifacts tab", () => {
  beforeEach(() => {
    getMock.mockReset();
    getMock.mockResolvedValue({
      id: "quality-report.md",
      name: "quality-report.md",
      type: "report",
      content: "# QA Report",
      truncated: false,
    });
  });

  it("uses the step artifact filename for content lookup and renders normalized artifact fields", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ArtifactsTab protocolId={35} />
      </QueryClientProvider>
    );

    expect(screen.getByText("quality-report.md")).toBeTruthy();
    expect(screen.getByText("report")).toBeTruthy();
    expect(screen.getByText("458 B")).toBeTruthy();

    fireEvent.click(screen.getByTitle("View artifact"));

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/steps/92/artifacts/quality-report.md/content");
    });
    expect(await screen.findByText("# QA Report")).toBeTruthy();
  });
});
