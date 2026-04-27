import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SpecWorkflow } from "@/components/speckit/spec-workflow";

describe("SpecWorkflow entry points", () => {
  it("routes spec to the canonical workflow and keeps plan/tasks in the spec workspace", () => {
    render(<SpecWorkflow projectId={12} showActions={false} />);

    expect(screen.getByRole("link", { name: /specification/i }).getAttribute("href")).toBe(
      "/projects/12?wizard=generate-specs&tab=spec"
    );
    expect(screen.getByRole("link", { name: /implementation plan/i }).getAttribute("href")).toBe(
      "/projects/12?tab=spec&step=plan"
    );
    expect(screen.getByRole("link", { name: /task list/i }).getAttribute("href")).toBe(
      "/projects/12?tab=spec&step=tasks"
    );
  });
});
