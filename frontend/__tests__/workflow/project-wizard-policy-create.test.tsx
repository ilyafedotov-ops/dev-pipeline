import type React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectWizard } from "@/components/wizards/project-wizard";

const pushMock = vi.fn();
const createProjectMutateAsyncMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/hooks/use-policy-packs", () => ({
  usePolicyPacks: () => ({
    data: [
      {
        id: 1,
        key: "default",
        version: "1.0",
        name: "General Purpose",
        description: "Balanced defaults",
        status: "active",
        is_builtin: true,
        editable: false,
        project_classification: "default",
        pack: {},
        created_at: "2026-04-21T00:00:00Z",
        updated_at: "2026-04-21T00:00:00Z",
      },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/lib/api/hooks/use-projects", () => ({
  useCreateProject: () => ({
    mutateAsync: createProjectMutateAsyncMock,
    isPending: false,
  }),
}));

describe("ProjectWizard policy-aware creation", () => {
  beforeEach(() => {
    pushMock.mockReset();
    createProjectMutateAsyncMock.mockReset();
    createProjectMutateAsyncMock.mockResolvedValue({ id: 123 });
  });

  it("submits classification and enforcement mode in the initial create payload", async () => {
    const onOpenChange = vi.fn();

    render(<ProjectWizard open onOpenChange={onOpenChange} />);

    fireEvent.change(screen.getByLabelText(/repository url/i), {
      target: { value: "https://github.com/example/platform.git" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^next$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^next$/i }));
    fireEvent.click(screen.getByRole("button", { name: /create project/i }));

    await waitFor(() => {
      expect(createProjectMutateAsyncMock).toHaveBeenCalledWith({
        name: "platform",
        git_url: "https://github.com/example/platform.git",
        github_token: undefined,
        base_branch: "main",
        project_classification: "default",
        policy_enforcement_mode: "warn",
        auto_onboard: true,
        auto_discovery: true,
      });
    });

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(pushMock).toHaveBeenCalledWith("/projects/123/onboarding");
  });
});
