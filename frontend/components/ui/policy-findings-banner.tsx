"use client";

import { useState } from "react";
import { AlertCircle, AlertTriangle, ChevronDown, Info } from "lucide-react";

import type { PolicyFinding } from "@/lib/api/types";

interface PolicyFindingsBannerProps {
  findings: PolicyFinding[];
  scope?: "step" | "protocol" | "project";
}

function severityIcon(severity: string, className?: string) {
  switch (severity) {
    case "error":
      return <AlertCircle className={className ?? "h-4 w-4 text-destructive shrink-0"} />;
    case "warning":
      return <AlertTriangle className={className ?? "h-4 w-4 text-yellow-500 shrink-0"} />;
    default:
      return <Info className={className ?? "h-4 w-4 text-blue-500 shrink-0"} />;
  }
}

export function PolicyFindingsBanner({ findings, scope }: PolicyFindingsBannerProps) {
  const [expanded, setExpanded] = useState(false);

  if (!findings || findings.length === 0) return null;

  const errors = findings.filter((f) => f.severity === "error").length;
  const warnings = findings.filter((f) => f.severity === "warning").length;
  const infos = findings.filter((f) => f.severity === "info").length;
  const hasErrors = errors > 0;

  const visible = expanded ? findings : findings.slice(0, 3);
  const remaining = findings.length - 3;

  const borderColor = hasErrors ? "border-l-destructive" : "border-l-yellow-500";
  const bgColor = hasErrors ? "bg-destructive/5" : "bg-yellow-500/5";

  return (
    <div className={`rounded-md border border-l-4 ${borderColor} ${bgColor} p-3`}>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm font-medium">
          {hasErrors ? (
            <AlertCircle className="h-4 w-4 text-destructive" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          )}
          <span>Policy Findings</span>
          <span className="text-muted-foreground font-normal">
            {errors > 0 && `${errors} error${errors !== 1 ? "s" : ""}`}
            {errors > 0 && warnings > 0 && ", "}
            {warnings > 0 && `${warnings} warning${warnings !== 1 ? "s" : ""}`}
            {errors === 0 && warnings === 0 && infos > 0 && `${infos} info`}
          </span>
        </div>
        <a
          href="#policy"
          className="text-muted-foreground text-xs hover:underline"
        >
          View details
        </a>
      </div>
      <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
        {visible.map((f, i) => (
          <div key={`${f.code}-${i}`} className="flex items-start gap-2 text-sm">
            {severityIcon(f.severity, "h-3.5 w-3.5 mt-0.5 shrink-0")}
            <code className="text-xs font-mono bg-muted rounded px-1 py-0.5 shrink-0">
              {f.code}
            </code>
            <span className="text-muted-foreground truncate" title={f.message}>
              {f.message.length > 80 ? f.message.slice(0, 80) + "…" : f.message}
            </span>
          </div>
        ))}
      </div>
      {remaining > 0 && !expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-muted-foreground mt-2 flex items-center gap-1 text-xs hover:underline"
        >
          <ChevronDown className="h-3 w-3" />
          Show {remaining} more…
        </button>
      )}
    </div>
  );
}
