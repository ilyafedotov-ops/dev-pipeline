"use client";

import { Fragment } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ChevronRight, Home } from "lucide-react";

const labelMap: Record<string, string> = {
  projects: "Projects",
  protocols: "Protocols",
  templates: "Templates",
  specifications: "Specifications",
  clarifications: "Clarifications",
  executions: "Executions",
  steps: "Steps",
  runs: "Runs",
  ops: "Operations",
  queues: "Queues",
  events: "Events",
  metrics: "Metrics",
  "policy-packs": "Policy Packs",
  settings: "Settings",
  profile: "Profile",
  onboarding: "Onboarding",
  branches: "Branches",
  policy: "Policy",
  spec: "Specification",
  logs: "Logs",
  artifacts: "Artifacts",
  execution: "Execution",
  quality: "Quality",
  agents: "Agents",
  sprints: "Execution",
  "sprint-board": "Execution",
};

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  const breadcrumbs = segments.map((segment, index) => {
    const href = `/${  segments.slice(0, index + 1).join("/")}`;
    const label =
      labelMap[segment] || segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ");
    const isLast = index === segments.length - 1;

    return { href, label, isLast };
  });

  return (
    <nav
      data-breadcrumbs
      className="bg-muted/30 flex items-center gap-2 border-b px-6 py-3 text-sm"
    >
      <Link href="/" className="text-muted-foreground hover:text-foreground transition-colors">
        <Home className="h-4 w-4" />
      </Link>
      {breadcrumbs.map((crumb) => (
        <Fragment key={crumb.href}>
          <ChevronRight className="text-muted-foreground h-4 w-4" />
          {crumb.isLast ? (
            <span className="text-foreground font-medium">{crumb.label}</span>
          ) : (
            <Link
              href={crumb.href}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {crumb.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
