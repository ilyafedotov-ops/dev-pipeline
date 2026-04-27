/**
 * Adapters for transforming backend API responses to frontend types.
 *
 * These adapters handle:
 * - Flattening nested structures (e.g., speckit_metadata)
 * - Mapping field name differences
 * - Providing defaults for optional fields
 */

import type { CodexRun, ProtocolArtifact, ProtocolRun } from "../types";

// Raw backend response types
export interface RawProtocolRun {
  id: number;
  project_id: number;
  protocol_name: string;
  status: string;
  base_branch: string;
  worktree_path: string | null;
  protocol_root?: string | null;
  description?: string | null;
  template_config?: Record<string, unknown> | null;
  template_source?: unknown | null;
  spec_hash?: string | null;
  spec_validation_status?: string | null;
  spec_validated_at?: string | null;
  policy_pack_key?: string | null;
  policy_pack_version?: string | null;
  policy_effective_hash?: string | null;
  policy_effective_json?: Record<string, unknown> | null;
  windmill_flow_id: string | null;
  speckit_metadata: Record<string, unknown> | null;
  summary?: string | null;
  linked_sprint_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface RawProtocolArtifact {
  id: string;
  step_run_id: number;
  step_name: string | null;
  type: string;
  name: string;
  size: number;
  created_at: string | null;
}

function getMetaString(meta: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = meta[key];
    if (typeof value === "string") {
      return value;
    }
  }
  return null;
}

function getMetaRecord(
  meta: Record<string, unknown>,
  ...keys: string[]
): Record<string, unknown> | null {
  for (const key of keys) {
    const value = meta[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value as Record<string, unknown>;
    }
  }
  return null;
}

function normalizeTemplateSource(value: unknown): string | null {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return null;
}

/**
 * Adapt a raw protocol run from the backend to the frontend ProtocolRun type.
 *
 * Handles:
 * - Flattening speckit_metadata fields (spec_hash, validation_status, etc.)
 * - Mapping windmill_flow_id to flow info
 */
export function adaptProtocol(data: RawProtocolRun): ProtocolRun {
  const meta = data.speckit_metadata || {};
  const templateSource = data.template_source ?? meta.template_source ?? null;

  return {
    id: data.id,
    project_id: data.project_id,
    protocol_name: data.protocol_name,
    status: data.status as ProtocolRun["status"],
    base_branch: data.base_branch,
    worktree_path: data.worktree_path,
    windmill_flow_id: data.windmill_flow_id,

    // Summary from backend
    summary: data.summary ?? null,

    // Speckit metadata (raw, for frontend access)
    speckit_metadata: data.speckit_metadata,

    // Flatten speckit_metadata for backwards compatibility
    spec_hash: data.spec_hash ?? getMetaString(meta, "spec_hash"),
    spec_validation_status:
      data.spec_validation_status ??
      getMetaString(meta, "spec_validation_status", "validation_status"),
    spec_validated_at:
      data.spec_validated_at ?? getMetaString(meta, "spec_validated_at", "validated_at"),

    // Template info from direct protocol fields, falling back to legacy metadata
    template_source: normalizeTemplateSource(templateSource),
    template_config: data.template_config ?? getMetaRecord(meta, "template_config"),

    // Protocol root
    protocol_root: data.protocol_root ?? getMetaString(meta, "protocol_root"),

    // Description/summary
    description: data.description ?? data.summary ?? getMetaString(meta, "description"),

    // Policy fields
    policy_pack_key: data.policy_pack_key ?? getMetaString(meta, "policy_pack_key"),
    policy_pack_version: data.policy_pack_version ?? getMetaString(meta, "policy_pack_version"),
    policy_effective_hash:
      data.policy_effective_hash ?? getMetaString(meta, "policy_effective_hash"),
    policy_effective_json:
      data.policy_effective_json ?? getMetaRecord(meta, "policy_effective_json"),

    // Linked sprint
    linked_sprint_id: data.linked_sprint_id ?? null,

    created_at: data.created_at,
    updated_at: data.updated_at,
  };
}

/**
 * Adapt an array of protocol runs.
 */
export function adaptProtocols(data: RawProtocolRun[]): ProtocolRun[] {
  return data.map(adaptProtocol);
}

/**
 * Adapt a raw protocol artifact from the backend.
 */
export function adaptProtocolArtifact(
  data: RawProtocolArtifact,
  protocolRunId: number
): ProtocolArtifact {
  return {
    id: data.id,
    protocol_run_id: protocolRunId,
    step_run_id: data.step_run_id,
    run_id: null,
    name: data.name,
    type: data.type,
    kind: data.type, // Alias for backwards compatibility
    size: data.size,
    bytes: data.size, // Alias for backwards compatibility
    created_at: data.created_at ?? new Date().toISOString(),
  };
}

/**
 * Adapt an array of protocol artifacts.
 */
export function adaptProtocolArtifacts(
  data: RawProtocolArtifact[],
  protocolRunId: number
): ProtocolArtifact[] {
  return data.map((a) => adaptProtocolArtifact(a, protocolRunId));
}

// Re-export types for convenience
export type { CodexRun, ProtocolArtifact, ProtocolRun };
