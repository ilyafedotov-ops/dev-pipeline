import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";
import { useStartBrownfieldRun } from "@/lib/api/hooks/use-projects";
import {
  useCreateProtocolFromSpec,
  useProjectProtocols,
  useProtocol,
} from "@/lib/api/hooks/use-protocols";
import { queryKeys } from "@/lib/api/query-keys";
import type { ProtocolRun } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return {
    queryClient,
    Wrapper,
  };
}

const rawProtocolResponse = {
  id: 42,
  project_id: 7,
  protocol_name: "Brownfield Auth Flow",
  status: "running",
  base_branch: "main",
  worktree_path: "/tmp/worktrees/auth",
  protocol_root: "/tmp/worktrees/auth/.devgodzilla/protocols/auth-flow",
  description: "Implement brownfield authentication flow",
  template_config: {
    mode: "brownfield",
  },
  template_source: {
    kind: "builtin",
    name: "brownfield/default",
  },
  summary: "Protocol summary",
  windmill_flow_id: "flow-123",
  speckit_metadata: {
    spec_run_id: 91,
    spec_hash: "abc123",
    validation_status: "validated",
    validated_at: "2026-03-09T10:00:00Z",
  },
  policy_pack_key: "repo/default",
  policy_pack_version: "1.0.0",
  policy_effective_hash: "policy-hash",
  policy_effective_json: {
    mode: "warn",
  },
  linked_sprint_id: 14,
  created_at: "2026-03-09T09:00:00Z",
  updated_at: "2026-03-09T10:00:00Z",
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("protocol API boundary adapters", () => {
  it("adapts flattened spec metadata for protocol detail responses", async () => {
    vi.mocked(apiClient.get).mockResolvedValue(rawProtocolResponse);
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useProtocol(42), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.data?.spec_hash).toBe("abc123");
      expect(result.current.data?.spec_validation_status).toBe("validated");
      expect(result.current.data?.spec_validated_at).toBe("2026-03-09T10:00:00Z");
      expect(result.current.data?.template_source).toBe(
        JSON.stringify(rawProtocolResponse.template_source)
      );
    });
  });

  it("adapts flattened spec metadata for project protocol lists", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([rawProtocolResponse]);
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useProjectProtocols(7), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.data).toEqual([
        expect.objectContaining({
          id: 42,
          spec_hash: "abc123",
          linked_sprint_id: 14,
        }),
      ]);
    });
  });

  it("adapts nested protocol payloads returned by create-from-spec", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      success: true,
      protocol: rawProtocolResponse,
      protocol_root: rawProtocolResponse.protocol_root,
      step_count: 4,
      warnings: [],
    });
    const { Wrapper } = createWrapper();

    const { result } = renderHook(() => useCreateProtocolFromSpec(), {
      wrapper: Wrapper,
    });

    let response:
      | Awaited<ReturnType<typeof result.current.mutateAsync>>
      | undefined;

    await act(async () => {
      response = await result.current.mutateAsync({
        project_id: 7,
        spec_run_id: 91,
      });
    });

    expect(response?.protocol).toMatchObject({
      id: 42,
      spec_hash: "abc123",
      linked_sprint_id: 14,
      template_source: JSON.stringify(rawProtocolResponse.template_source),
    });
  });

  it("writes adapted protocol payloads into brownfield protocol caches", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      success: true,
      project_id: 7,
      output_mode: "protocol",
      spec_run_id: 91,
      spec_path: null,
      plan_path: null,
      tasks_path: null,
      protocol: rawProtocolResponse,
      task_ids: [],
      work_items: [],
      next_work_item_id: null,
      warnings: [],
    });
    const { queryClient, Wrapper } = createWrapper();

    const { result } = renderHook(() => useStartBrownfieldRun(), {
      wrapper: Wrapper,
    });

    let response:
      | Awaited<ReturnType<typeof result.current.mutateAsync>>
      | undefined;

    await act(async () => {
      response = await result.current.mutateAsync({
        projectId: 7,
        data: {
          feature_request: "Add brownfield auth flow",
        },
      });
    });

    const cachedProtocols = queryClient.getQueryData(
      queryKeys.projects.protocols(7)
    ) as ProtocolRun[] | undefined;

    expect(response?.protocol).toMatchObject({
      id: 42,
      spec_hash: "abc123",
      linked_sprint_id: 14,
      template_source: JSON.stringify(rawProtocolResponse.template_source),
    });
    expect(cachedProtocols).toEqual([
      expect.objectContaining({
        id: 42,
        spec_hash: "abc123",
        linked_sprint_id: 14,
      }),
    ]);
  });
});
