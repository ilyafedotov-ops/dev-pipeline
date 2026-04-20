/**
 * Shared utilities for rendering event/log metadata in a structured way.
 * Used by both the Events page and the EventFeed component.
 */
import React from "react";

import { Badge } from "@/components/ui/badge";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

export function formatMetadataValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (key.includes("duration") || key.includes("time")) {
      if (value < 1000) return `${value}ms`;
      if (value < 60000) return `${(value / 1000).toFixed(1)}s`;
      return `${(value / 60000).toFixed(1)}m`;
    }
    if (key.includes("cost") || key.includes("price") || key.includes("cents")) {
      return `$${(value / 100).toFixed(4)}`;
    }
    if (key.includes("tokens")) {
      return value.toLocaleString();
    }
    return String(value);
  }
  if (typeof value === "string") {
    if (value.length > 120) return `${value.slice(0, 120)}…`;
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    if (value.length <= 3) return value.join(", ");
    return `${value.slice(0, 3).join(", ")} +${value.length - 3} more`;
  }
  return JSON.stringify(value);
}

export function formatKeyLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Duration formatting
// ---------------------------------------------------------------------------

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

// ---------------------------------------------------------------------------
// Known metadata keys that are rendered as dedicated badges/sections
// ---------------------------------------------------------------------------

const KNOWN_KEYS = new Set([
  "error",
  "duration_ms",
  "duration_s",
  "agent_id",
  "step_name",
  "job_type",
  "run_id",
  "model",
  "cost_tokens",
  "cost_cents",
  "score",
  "gate_name",
  "findings",
  "status",
  "engine_id",
  "exit_code",
]);

// ---------------------------------------------------------------------------
// Status badge helper
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const variant =
    s === "passed" || s === "completed" || s === "success" || s === "succeeded"
      ? "default"
      : s === "failed" || s === "error"
        ? "destructive"
        : "secondary";
  return (
    <Badge variant={variant} className="text-[10px]">
      {status}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Structured metadata renderer for events
// ---------------------------------------------------------------------------

export function renderStructuredMetadata(
  metadata: Record<string, unknown> | null | undefined
): React.ReactNode {
  if (!metadata || Object.keys(metadata).length === 0) return null;

  const m = metadata as Record<string, unknown>;
  const badges: React.ReactNode[] = [];
  const sections: React.ReactNode[] = [];
  const remaining: Array<{ key: string; value: unknown }> = [];

  // --- Error ---
  if (m.error) {
    badges.push(
      <Badge key="error" variant="destructive" className="text-[10px]">
        Error: {String(m.error).length > 80 ? `${String(m.error).slice(0, 80)}…` : String(m.error)}
      </Badge>
    );
  }

  // --- Duration ---
  if (m.duration_ms != null && typeof m.duration_ms === "number") {
    badges.push(
      <Badge key="duration" variant="secondary" className="text-[10px]">
        ⏱ {formatDuration(m.duration_ms)}
      </Badge>
    );
  } else if (m.duration_s != null && typeof m.duration_s === "number") {
    badges.push(
      <Badge key="duration" variant="secondary" className="text-[10px]">
        ⏱ {formatDuration(m.duration_s * 1000)}
      </Badge>
    );
  }

  // --- Agent ---
  if (m.agent_id) {
    badges.push(
      <Badge key="agent" variant="outline" className="text-[10px]">
        🤖 {String(m.agent_id)}
      </Badge>
    );
  }

  // --- Step name ---
  if (m.step_name) {
    badges.push(
      <Badge key="step" variant="outline" className="text-[10px]">
        📋 {String(m.step_name)}
      </Badge>
    );
  }

  // --- Job type ---
  if (m.job_type) {
    badges.push(
      <Badge key="jobtype" variant="outline" className="text-[10px]">
        ⚡ {String(m.job_type)}
      </Badge>
    );
  }

  // --- Run ID ---
  if (m.run_id) {
    badges.push(
      <Link key="runid" href={`/runs/${String(m.run_id)}`} className="inline-flex">
        <Badge variant="outline" className="text-[10px] hover:bg-muted">
          🔗 {String(m.run_id).slice(0, 12)}
        </Badge>
      </Link>
    );
  }

  // --- Model ---
  if (m.model) {
    badges.push(
      <Badge key="model" variant="outline" className="text-[10px]">
        🧠 {String(m.model)}
      </Badge>
    );
  }

  // --- Cost ---
  if (m.cost_tokens != null || m.cost_cents != null) {
    const parts: string[] = [];
    if (m.cost_tokens != null) parts.push(`${Number(m.cost_tokens).toLocaleString()} tokens`);
    if (m.cost_cents != null) parts.push(`$${(Number(m.cost_cents) / 100).toFixed(4)}`);
    badges.push(
      <Badge key="cost" variant="secondary" className="text-[10px]">
        💰 {parts.join(" · ")}
      </Badge>
    );
  }

  // --- Score ---
  if (m.score != null) {
    badges.push(
      <Badge key="score" variant="secondary" className="text-[10px]">
        📊 Score: {String(m.score)}
      </Badge>
    );
  }

  // --- Gate ---
  if (m.gate_name) {
    badges.push(
      <Badge key="gate" variant="outline" className="text-[10px]">
        🛡 {String(m.gate_name)}
      </Badge>
    );
  }

  // --- Status ---
  if (m.status && typeof m.status === "string") {
    badges.push(<StatusBadge key="status" status={String(m.status)} />);
  }

  // --- Engine ID ---
  if (m.engine_id) {
    badges.push(
      <Badge key="engine" variant="outline" className="text-[10px]">
        ⚙ {String(m.engine_id)}
      </Badge>
    );
  }

  // --- Exit code ---
  if (m.exit_code !== undefined && m.exit_code !== null) {
    const isOk = Number(m.exit_code) === 0;
    badges.push(
      <Badge key="exitcode" variant={isOk ? "default" : "destructive"} className="text-[10px]">
        Exit: {String(m.exit_code)}
      </Badge>
    );
  }

  // --- Findings ---
  if (Array.isArray(m.findings) && m.findings.length > 0) {
    sections.push(
      <div key="findings-section" className="space-y-1">
        <span className="text-muted-foreground text-xs font-medium">
          Findings ({m.findings.length}):
        </span>
        <ul className="list-inside list-disc space-y-0.5 pl-2 text-xs">
          {m.findings.map((f: unknown, i: number) => {
            const text =
              typeof f === "object" && f !== null
                ? String((f as Record<string, unknown>).message ?? (f as Record<string, unknown>).severity ?? JSON.stringify(f))
                : String(f);
            return (
              <li key={i} className="text-muted-foreground">
                {text}
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  // --- Remaining fields ---
  for (const [key, value] of Object.entries(m)) {
    if (value === null || value === undefined) continue;
    if (KNOWN_KEYS.has(key)) continue;
    // Skip findings since handled above
    if (key === "findings") continue;
    remaining.push({ key, value });
  }

  // Build output
  const parts: React.ReactNode[] = [];

  if (badges.length > 0) {
    parts.push(
      <div key="badges" className="flex flex-wrap gap-1.5">
        {badges}
      </div>
    );
  }

  if (sections.length > 0) {
    parts.push(...sections);
  }

  if (remaining.length > 0) {
    parts.push(
      <details key="remaining" className="group">
        <summary className="text-muted-foreground cursor-pointer text-xs hover:text-foreground">
          More fields ({remaining.length})
        </summary>
        <div className="bg-muted mt-2 grid grid-cols-2 gap-x-4 gap-y-1 rounded p-2 text-xs md:grid-cols-3">
          {remaining.map(({ key, value }) => (
            <div key={key} className="flex gap-1">
              <span className="text-muted-foreground">{formatKeyLabel(key)}:</span>
              <span className="truncate font-medium">{formatMetadataValue(key, value)}</span>
            </div>
          ))}
        </div>
      </details>
    );
  }

  return parts.length > 0 ? <div className="space-y-2">{parts}</div> : null;
}
