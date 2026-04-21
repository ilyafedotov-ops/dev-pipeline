import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";
import { useProjectClarifications } from "@/lib/api/hooks/use-projects";
import { useProtocolClarifications } from "@/lib/api/hooks/use-protocols";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("clarification filter hooks", () => {
  it("omits the project clarification status query when filter is all", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([]);

    renderHook(() => useProjectClarifications(12, "all"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/projects/12/clarifications");
    });
  });

  it("omits the protocol clarification status query when filter is all", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([]);

    renderHook(() => useProtocolClarifications(34, "all"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/protocols/34/clarifications");
    });
  });

  it("preserves explicit status filters for project clarifications", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([]);

    renderHook(() => useProjectClarifications(56, "open"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/projects/56/clarifications?status=open");
    });
  });
});
