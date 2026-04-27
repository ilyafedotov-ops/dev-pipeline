"use client";

import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AlertCircle, Loader2, RotateCcw, Save, Settings2, TestTube2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type Agent,
  type AgentUpdate,
  useAgent,
  useAgents,
  useAgentModels,
  useRefreshAgentModels,
  useTestAgentSetup,
  useUpdateAgentConfig,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface AgentConfigManagerProps {
  /** Project ID for project-scoped configuration */
  projectId?: number;
  /** Specific agent ID to configure. If omitted, shows a list to choose from */
  agentId?: string;
  /** Callback when an agent is selected from the list */
  onAgentSelect?: (agentId: string) => void;
  className?: string;
}

interface ConfigFormData {
  default_model: string;
  reasoning_effort: string;
  timeout_seconds: string;
  max_retries: string;
  sandbox: string;
  endpoint: string;
  command: string;
  command_dir: string;
  format: string;
  enabled: boolean;
  capabilities: string; // comma-separated
}

// =============================================================================
// Constants
// =============================================================================

const FALLBACK_MODELS_BY_AGENT: Record<string, string[]> = {
  codex: ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.2", "codex-auto-review"],
  opencode: ["openai/gpt-5", "openai/gpt-4.1", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro"],
  "claude-code": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
  "gemini-cli": ["gemini-2.5-pro", "gemini-2.5-flash"],
};

const SANDBOX_OPTIONS = [
  { value: "none", label: "No Sandbox" },
  { value: "docker", label: "Docker" },
  { value: "nsjail", label: "nsjail" },
  { value: "firejail", label: "Firejail" },
];

const FORMAT_OPTIONS = [
  { value: "markdown", label: "Markdown" },
  { value: "json", label: "JSON" },
  { value: "xml", label: "XML" },
  { value: "plain", label: "Plain Text" },
];

const DEFAULT_TIMEOUT = 300;
const DEFAULT_MAX_RETRIES = 2;

// =============================================================================
// AgentConfigForm Component
// =============================================================================

interface AgentConfigFormProps {
  agent: Agent;
  projectId?: number;
  onSaved?: () => void;
}

export function AgentConfigForm({ agent, projectId, onSaved }: AgentConfigFormProps) {
  const updateConfig = useUpdateAgentConfig();
  const testSetup = useTestAgentSetup();
  const modelList = useAgentModels(agent.id, projectId);
  const refreshModels = useRefreshAgentModels();

  const [form, setForm] = useState<ConfigFormData>({
    default_model: agent.default_model ?? "",
    reasoning_effort: agent.reasoning_effort ?? "",
    timeout_seconds: String(agent.timeout_seconds ?? DEFAULT_TIMEOUT),
    max_retries: String(agent.max_retries ?? DEFAULT_MAX_RETRIES),
    sandbox: agent.sandbox ?? "none",
    endpoint: agent.endpoint ?? "",
    command: agent.command ?? "",
    command_dir: agent.command_dir ?? "",
    format: agent.format ?? "markdown",
    enabled: agent.enabled ?? agent.status !== "disabled",
    capabilities: agent.capabilities?.join(", ") ?? "",
  });

  const [hasChanges, setHasChanges] = useState(false);
  const [lastModelsRefreshAt, setLastModelsRefreshAt] = useState<string | null>(null);

  // Sync form when agent data changes
  useEffect(() => {
    setForm({
      default_model: agent.default_model ?? "",
      reasoning_effort: agent.reasoning_effort ?? "",
      timeout_seconds: String(agent.timeout_seconds ?? DEFAULT_TIMEOUT),
      max_retries: String(agent.max_retries ?? DEFAULT_MAX_RETRIES),
      sandbox: agent.sandbox ?? "none",
      endpoint: agent.endpoint ?? "",
      command: agent.command ?? "",
      command_dir: agent.command_dir ?? "",
      format: agent.format ?? "markdown",
      enabled: agent.enabled ?? agent.status !== "disabled",
      capabilities: agent.capabilities?.join(", ") ?? "",
    });
    setHasChanges(false);
  }, [agent]);

  const updateField = useCallback(<K extends keyof ConfigFormData>(key: K, value: ConfigFormData[K]) => {
    if (updateConfig.error) {
      updateConfig.reset();
    }
    if (testSetup.error) {
      testSetup.reset();
    }
    setForm((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  }, [updateConfig, testSetup]);

  const buildUpdatePayload = useCallback((): AgentUpdate => {
    return {
      default_model: form.default_model || null,
      reasoning_effort: form.reasoning_effort || null,
      timeout_seconds: parseInt(form.timeout_seconds, 10) || DEFAULT_TIMEOUT,
      max_retries: parseInt(form.max_retries, 10) || DEFAULT_MAX_RETRIES,
      sandbox: form.sandbox === "none" ? null : form.sandbox,
      endpoint: form.endpoint || null,
      command: form.command || null,
      command_dir: form.command_dir || null,
      format: form.format || null,
      enabled: form.enabled,
      capabilities: form.capabilities
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
  }, [form]);

  const handleSave = useCallback(async () => {
    try {
      updateConfig.reset();
      testSetup.reset();
      await updateConfig.mutateAsync({
        agentId: agent.id,
        data: buildUpdatePayload(),
        projectId,
      });
      setHasChanges(false);
      onSaved?.();
    } catch {
      // Error is handled by mutation state
    }
  }, [updateConfig, testSetup, agent.id, buildUpdatePayload, projectId, onSaved]);

  const handleReset = useCallback(() => {
    updateConfig.reset();
    testSetup.reset();
    setForm({
      default_model: agent.default_model ?? "",
      reasoning_effort: agent.reasoning_effort ?? "",
      timeout_seconds: String(agent.timeout_seconds ?? DEFAULT_TIMEOUT),
      max_retries: String(agent.max_retries ?? DEFAULT_MAX_RETRIES),
      sandbox: agent.sandbox ?? "none",
      endpoint: agent.endpoint ?? "",
      command: agent.command ?? "",
      command_dir: agent.command_dir ?? "",
      format: agent.format ?? "markdown",
      enabled: agent.enabled ?? agent.status !== "disabled",
      capabilities: agent.capabilities?.join(", ") ?? "",
    });
    setHasChanges(false);
  }, [agent, updateConfig, testSetup]);

  const handleTest = useCallback(async () => {
    updateConfig.reset();
    testSetup.reset();
    await testSetup.mutateAsync({
      agentId: agent.id,
      projectId,
      overrides: buildUpdatePayload(),
    });
  }, [updateConfig, testSetup, agent.id, projectId, buildUpdatePayload]);

  const isSaving = updateConfig.isPending;
  const isTesting = testSetup.isPending;
  const modelSource = modelList.data?.source;
  const fallbackModels = agent.id === "codex" || ["cli", "cache", "bundle", "provider_api"].includes(modelSource ?? "")
    ? []
    : (FALLBACK_MODELS_BY_AGENT[agent.id] ?? []);
  const availableModels = Array.from(new Set([...(modelList.data?.models ?? []), ...fallbackModels]));
  const hasInvalidCurrentModel = !!form.default_model && !availableModels.includes(form.default_model);
  const selectedModelDetails = (form.default_model && modelList.data?.model_details?.[form.default_model]) || null;
  const reasoningOptions = selectedModelDetails?.supported_reasoning_efforts ?? [];
  const effectiveReasoningValue = form.reasoning_effort || selectedModelDetails?.default_reasoning_effort || "";

  const handleRefreshModels = useCallback(async () => {
    toast.loading("Refreshing models...", { id: "agent-model-refresh" });
    try {
      const refreshed = await refreshModels.mutateAsync({ agentId: agent.id, projectId });
      setLastModelsRefreshAt(new Date().toLocaleTimeString());
      toast.success(`Models refreshed (${refreshed.models.length})`, { id: "agent-model-refresh" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to refresh models";
      toast.error(message, { id: "agent-model-refresh" });
    }
  }, [refreshModels, agent.id, projectId]);

  return (
    <div className="space-y-6">
      {/* Error display */}
      {(updateConfig.error || testSetup.error) && (
        <div className="bg-destructive/10 text-destructive flex items-start gap-2 rounded-md p-3 text-sm">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {(updateConfig.error instanceof Error ? updateConfig.error.message : null) ||
              (testSetup.error instanceof Error ? testSetup.error.message : null) ||
              "An error occurred"}
          </span>
        </div>
      )}

      {/* Test result */}
      {testSetup.data && (
        <div
          className={cn(
            "rounded-md p-3 text-sm",
            testSetup.data.ok
              ? "bg-green-500/10 text-green-700 dark:text-green-400"
              : "bg-destructive/10 text-destructive",
          )}
        >
          <div className="flex items-center gap-2 font-medium">
            <TestTube2 className="h-4 w-4" />
            {testSetup.data.ok ? "All checks passed" : "Some checks failed"}
            {testSetup.data.duration_ms != null && (
              <Badge variant="outline" className="text-xs">
                {testSetup.data.duration_ms}ms
              </Badge>
            )}
          </div>
          {testSetup.data.checks.length > 0 && (
            <ul className="mt-2 space-y-1">
              {testSetup.data.checks.map((check, i) => (
                <li key={i} className="flex items-center gap-2 text-xs">
                  <span className={check.ok ? "text-green-600" : "text-red-600"}>
                    {check.ok ? "✓" : "✗"}
                  </span>
                  <span>{check.name}</span>
                  {check.error && (
                    <span className="text-muted-foreground">— {check.error}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Enable/Disable toggle */}
      <div className="flex items-center justify-between rounded-lg border p-4">
        <div className="space-y-0.5">
          <Label className="text-sm font-medium">Enabled</Label>
          <p className="text-muted-foreground text-xs">
            {form.enabled ? "Agent is active and can receive tasks" : "Agent is disabled and won't receive tasks"}
          </p>
        </div>
        <Switch
          checked={form.enabled}
          onCheckedChange={(checked) => updateField("enabled", checked)}
        />
      </div>

      {/* Model Configuration */}
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Model Configuration</h3>
          <Button type="button" variant="outline" size="sm" onClick={handleRefreshModels} disabled={refreshModels.isPending}>
            {refreshModels.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Refresh Models
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="model" className="text-xs">Default Model</Label>
            <Select
              value={hasInvalidCurrentModel ? undefined : form.default_model}
              onValueChange={(v) => updateField("default_model", v)}
            >
              <SelectTrigger id="model" className="text-sm">
                <SelectValue placeholder="Select model..." />
              </SelectTrigger>
              <SelectContent>
                {availableModels.map((model) => (
                  <SelectItem key={model} value={model}>
                    {model}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasInvalidCurrentModel && (
              <p className="text-destructive text-[10px]">
                Current model is not valid for this agent and is not included in the available model list.
              </p>
            )}
            <p className="text-muted-foreground text-[10px]">
              Source: {modelList.data?.source ?? "unknown"}.
              {modelList.data?.warning ? ` ${modelList.data.warning}` : ""}
            </p>
            {lastModelsRefreshAt && (
              <p className="text-muted-foreground text-[10px]">
                Refreshed at {lastModelsRefreshAt}
              </p>
            )}
            <p className="text-muted-foreground text-[10px]">
              You can still type a custom model below, but save/test will validate it against the agent source when supported.
            </p>
            <Input
              value={form.default_model}
              onChange={(e) => updateField("default_model", e.target.value)}
              placeholder="custom/model-name"
              className="h-8 text-xs"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="reasoning_effort" className="text-xs">Reasoning Effort</Label>
            <Select
              value={effectiveReasoningValue || undefined}
              onValueChange={(v) => updateField("reasoning_effort", v)}
              disabled={reasoningOptions.length === 0}
            >
              <SelectTrigger id="reasoning_effort" className="text-sm">
                <SelectValue placeholder={reasoningOptions.length === 0 ? "Not available for this model" : "Use model default"} />
              </SelectTrigger>
              <SelectContent>
                {reasoningOptions.map((opt) => (
                  <SelectItem key={opt.effort} value={opt.effort}>
                    {opt.effort}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedModelDetails?.default_reasoning_effort && (
              <p className="text-muted-foreground text-[10px]">
                Model default: {selectedModelDetails.default_reasoning_effort}
              </p>
            )}
            {reasoningOptions.length > 0 ? (
              <p className="text-muted-foreground text-[10px]">
                {reasoningOptions.find((opt) => opt.effort === effectiveReasoningValue)?.description ?? "Adjust how much the model reasons before responding."}
              </p>
            ) : (
              <p className="text-muted-foreground text-[10px]">
                Reasoning controls are only exposed when the agent source reports supported values.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Execution Settings */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Execution Settings</h3>

        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-2">
            <Label htmlFor="timeout" className="text-xs">Timeout (seconds)</Label>
            <Input
              id="timeout"
              type="number"
              min={10}
              max={3600}
              value={form.timeout_seconds}
              onChange={(e) => updateField("timeout_seconds", e.target.value)}
              className="h-9 text-sm"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="retries" className="text-xs">Max Retries</Label>
            <Input
              id="retries"
              type="number"
              min={0}
              max={10}
              value={form.max_retries}
              onChange={(e) => updateField("max_retries", e.target.value)}
              className="h-9 text-sm"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="sandbox" className="text-xs">Sandbox</Label>
            <Select value={form.sandbox} onValueChange={(v) => updateField("sandbox", v)}>
              <SelectTrigger id="sandbox" className="text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SANDBOX_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="format" className="text-xs">Output Format</Label>
            <Select value={form.format} onValueChange={(v) => updateField("format", v)}>
              <SelectTrigger id="format" className="text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FORMAT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Command Configuration */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Command & Endpoint</h3>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="command" className="text-xs">Command</Label>
            <Input
              id="command"
              value={form.command}
              onChange={(e) => updateField("command", e.target.value)}
              placeholder="e.g., opencode"
              className="h-9 text-sm font-mono"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="command_dir" className="text-xs">Command Directory</Label>
            <Input
              id="command_dir"
              value={form.command_dir}
              onChange={(e) => updateField("command_dir", e.target.value)}
              placeholder="/path/to/agent"
              className="h-9 text-sm font-mono"
            />
          </div>

          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="endpoint" className="text-xs">API Endpoint</Label>
            <Input
              id="endpoint"
              value={form.endpoint}
              onChange={(e) => updateField("endpoint", e.target.value)}
              placeholder="https://api.example.com/v1/agent"
              className="h-9 text-sm font-mono"
            />
          </div>
        </div>
      </div>

      {/* Capabilities */}
      <div className="space-y-2">
        <Label htmlFor="capabilities" className="text-xs font-semibold">Capabilities</Label>
        <Textarea
          id="capabilities"
          value={form.capabilities}
          onChange={(e) => updateField("capabilities", e.target.value)}
          placeholder="code_generation, testing, review, deployment"
          className="min-h-[60px] text-xs font-mono"
        />
        <p className="text-muted-foreground text-[10px]">Comma-separated list of agent capabilities</p>
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-between border-t pt-4">
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={isTesting}
          >
            {isTesting ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <TestTube2 className="mr-1 h-3.5 w-3.5" />
            )}
            Test Setup
          </Button>
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            disabled={isSaving || !hasChanges}
          >
            <RotateCcw className="mr-1 h-3.5 w-3.5" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving || !hasChanges}
          >
            {isSaving ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1 h-3.5 w-3.5" />
            )}
            Save Configuration
          </Button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function AgentConfigManager({
  projectId,
  agentId: initialAgentId,
  onAgentSelect,
  className,
}: AgentConfigManagerProps) {
  const { data: agents, isLoading: agentsLoading } = useAgents(projectId);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(initialAgentId ?? null);

  const { data: agentDetail, isLoading: agentLoading } = useAgent(selectedAgentId ?? undefined);

  // Sync with external agentId prop
  useEffect(() => {
    if (initialAgentId) {
      setSelectedAgentId(initialAgentId);
    }
  }, [initialAgentId]);

  const handleSelectAgent = useCallback(
    (id: string) => {
      setSelectedAgentId(id);
      onAgentSelect?.(id);
    },
    [onAgentSelect],
  );

  if (agentsLoading) {
    return <LoadingState message="Loading agents..." />;
  }

  // If we have a specific agent, show its config directly
  if (initialAgentId && agentLoading) {
    return <LoadingState message="Loading agent configuration..." />;
  }

  const selectedAgent =
    agentDetail ?? agents?.find((a) => a.id === selectedAgentId);

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings2 className="h-5 w-5" />
          Agent Configuration
        </CardTitle>
        <CardDescription>
          Configure model, timeout, sandbox, and execution settings per agent
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!agents || agents.length === 0 ? (
          <EmptyState
            icon={AlertCircle}
            title="No agents found"
            description="No agents are configured for this project"
          />
        ) : !initialAgentId ? (
          /* Agent list + config side by side */
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
            {/* Agent list sidebar */}
            <div className="space-y-1">
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  onClick={() => handleSelectAgent(agent.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
                    "hover:bg-muted",
                    agent.id === selectedAgentId && "bg-muted font-medium",
                  )}
                >
                  <span
                    className={cn(
                      "h-2 w-2 shrink-0 rounded-full",
                      agent.status === "available"
                        ? "bg-green-500"
                        : agent.status === "busy"
                          ? "bg-yellow-500"
                          : agent.status === "disabled"
                            ? "bg-gray-400"
                            : "bg-red-500",
                    )}
                  />
                  <span className="truncate">{agent.name}</span>
                  <Badge variant="secondary" className="ml-auto text-[10px]">
                    {agent.kind}
                  </Badge>
                </button>
              ))}
            </div>

            {/* Config form */}
            <div className="rounded-lg border p-4">
              {selectedAgent ? (
                <>
                  <div className="mb-4 flex items-center gap-3">
                    <div className="bg-muted flex h-10 w-10 shrink-0 items-center justify-center rounded-lg">
                      <Settings2 className="text-muted-foreground h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{selectedAgent.name}</h3>
                      <p className="text-muted-foreground text-xs">
                        ID: {selectedAgent.id} • Kind: {selectedAgent.kind}
                      </p>
                    </div>
                  </div>
                  <AgentConfigForm
                    agent={selectedAgent}
                    projectId={projectId}
                    onSaved={() => {}}
                  />
                </>
              ) : (
                <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
                  Select an agent to configure
                </div>
              )}
            </div>
          </div>
        ) : selectedAgent ? (
          /* Direct config for a specific agent */
          <AgentConfigForm agent={selectedAgent} projectId={projectId} />
        ) : (
          <EmptyState
            icon={AlertCircle}
            title="Agent not found"
            description={`Agent "${initialAgentId}" was not found`}
          />
        )}
      </CardContent>
    </Card>
  );
}
