import { Suspense } from "react";

import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ProtocolDetailPage from "@/app/protocols/[id]/page";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/websocket/hooks", () => ({
  useWebSocketEvent: () => {},
}));

vi.mock("@/lib/api", () => ({
  useProtocol: () => ({
    data: {
      id: 42,
      project_id: 12,
      protocol_name: "Auth Flow",
      status: "running",
      base_branch: "main",
      description: null,
      spec_hash: "abc123",
      policy_pack_key: null,
      template_source: '{"kind":"builtin","name":"brownfield/default"}',
      template_config: {
        mode: "brownfield",
        owner: "protocol",
      },
      speckit_metadata: {
        spec_run_id: 77,
      },
    },
    isLoading: false,
  }),
  useProject: () => ({
    data: {
      id: 12,
      name: "Demo Project",
    },
  }),
  useProtocolAction: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useProtocolFlow: () => ({
    data: null,
  }),
  useCreateProtocolFlow: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useProtocolSprint: () => ({
    data: null,
  }),
  useSyncProtocolToSprint: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useFeedbackEvents: () => ({ data: null }),
  useFeedbackAnswerClarification: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProtocolPolicyFindings: () => ({ data: null }),
}));

vi.mock("@/app/protocols/[id]/components/artifacts-tab", () => ({
  ArtifactsTab: () => <div>Artifacts</div>,
}));
vi.mock("@/app/protocols/[id]/components/clarifications-tab", () => ({
  ClarificationsTab: () => <div>Clarifications</div>,
}));
vi.mock("@/app/protocols/[id]/components/events-tab", () => ({
  EventsTab: () => <div>Events</div>,
}));
vi.mock("@/app/protocols/[id]/components/feedback-tab", () => ({
  FeedbackTab: () => <div>Feedback</div>,
}));
vi.mock("@/app/protocols/[id]/components/logs-tab", () => ({
  LogsTab: () => <div>Logs</div>,
}));
vi.mock("@/app/protocols/[id]/components/policy-tab", () => ({
  PolicyTab: () => <div>Policy</div>,
}));
vi.mock("@/app/protocols/[id]/components/quality-tab", () => ({
  QualityTab: () => <div>Quality</div>,
}));
vi.mock("@/app/protocols/[id]/components/runs-tab", () => ({
  RunsTab: () => <div>Runs</div>,
}));
vi.mock("@/app/protocols/[id]/components/spec-tab", () => ({
  SpecTab: () => <div>Spec</div>,
}));
vi.mock("@/app/protocols/[id]/components/steps-tab", () => ({
  StepsTab: () => <div>Steps</div>,
}));

describe("Protocol detail review link", () => {
  it("offers the canonical review entry point when the protocol is linked to a specification run", async () => {
    await act(async () => {
      render(
        <Suspense fallback={<div>Loading...</div>}>
          <ProtocolDetailPage params={Promise.resolve({ id: "42" })} />
        </Suspense>
      );
    });

    expect(
      (await screen.findByRole("link", { name: /review implementation/i })).getAttribute("href")
    ).toBe("/specifications/77?tab=analysis");
    expect(screen.getByText("Template Source")).toBeDefined();
    expect(screen.getByText("builtin: brownfield/default")).toBeDefined();
    expect(screen.getByText("Template Config")).toBeDefined();
    expect(screen.getByText("2 fields")).toBeDefined();
    expect(screen.getByText("mode=brownfield, owner=protocol")).toBeDefined();
  });
});
