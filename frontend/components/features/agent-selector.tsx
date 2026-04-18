"use client";

import { useMemo, useState } from "react";

import {
  AlertCircle,
  Bot,
  Cpu,
  Search,
  Settings2,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type Agent, useAgents } from "@/lib/api";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface AgentSelectorProps {
  projectId?: number;
  value?: string;
  onChange: (agentId: string) => void;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
  filterByCapability?: string;
  showStatus?: boolean;
  showModel?: boolean;
}

export interface AgentGridProps {
  projectId?: number;
  selectedAgentId?: string;
  onSelect: (agentId: string) => void;
  onConfigure?: (agentId: string) => void;
  className?: string;
  filterByCapability?: string;
}

export type AgentKind = "code_gen" | "planning" | "exec" | "qa" | "discovery";

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Gets the icon component for an agent kind
 */
export function getAgentKindIcon(kind: string) {
  switch (kind) {
    case "code_gen":
      return Cpu;
    case "planning":
      return Zap;
    case "exec":
      return Bot;
    case "qa":
      return AlertCircle;
    case "discovery":
      return Bot;
    default:
      return Bot;
  }
}

/**
 * Gets the display label for an agent kind
 */
export function getAgentKindLabel(kind: string): string {
  switch (kind) {
    case "code_gen":
      return "Code Generation";
    case "planning":
      return "Planning";
    case "exec":
      return "Execution";
    case "qa":
      return "Quality Assurance";
    case "discovery":
      return "Discovery";
    default:
      return kind;
  }
}

/**
 * Gets the status color for an agent
 */
export function getAgentStatusColor(status: string): string {
  switch (status) {
    case "available":
      return "bg-green-500";
    case "busy":
      return "bg-yellow-500";
    case "configured":
      return "bg-blue-500";
    case "unavailable":
      return "bg-red-500";
    case "disabled":
      return "bg-gray-400";
    default:
      return "bg-gray-500";
  }
}

/**
 * Gets the status badge variant for an agent
 */
export function getAgentStatusBadgeVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "available":
      return "default";
    case "busy":
      return "secondary";
    case "unavailable":
    case "disabled":
      return "destructive";
    default:
      return "outline";
  }
}

/**
 * Groups agents by their kind
 */
export function groupAgentsByKind(agents: Agent[]): Record<string, Agent[]> {
  return agents.reduce(
    (acc, agent) => {
      const kind = agent.kind || "other";
      if (!acc[kind]) {
        acc[kind] = [];
      }
      acc[kind].push(agent);
      return acc;
    },
    {} as Record<string, Agent[]>,
  );
}

/**
 * Filters agents by capability
 */
export function filterAgentsByCapability(agents: Agent[], capability: string): Agent[] {
  if (!capability) return agents;
  return agents.filter((agent) => agent.capabilities?.includes(capability) || false);
}

/**
 * Sorts agents by status (available first) then by name
 */
export function sortAgentsByStatusAndName(agents: Agent[]): Agent[] {
  const statusOrder = { available: 0, busy: 1, configured: 2, unavailable: 3, disabled: 4 };
  return [...agents].sort((a, b) => {
    const statusDiff =
      (statusOrder[a.status as keyof typeof statusOrder] ?? 5) -
      (statusOrder[b.status as keyof typeof statusOrder] ?? 5);
    if (statusDiff !== 0) return statusDiff;
    return a.name.localeCompare(b.name);
  });
}

// =============================================================================
// AgentCard Component (for grid view)
// =============================================================================

interface AgentCardProps {
  agent: Agent;
  selected: boolean;
  onSelect: () => void;
  onConfigure?: () => void;
}

function AgentCard({ agent, selected, onSelect, onConfigure }: AgentCardProps) {
  const KindIcon = getAgentKindIcon(agent.kind);
  const statusColor = getAgentStatusColor(agent.status);
  const isDisabled = agent.status === "unavailable" || agent.status === "disabled";

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={isDisabled}
      className={cn(
        "group w-full rounded-lg border p-4 text-left transition-all",
        "hover:border-primary/50 hover:shadow-sm",
        "focus:outline-none focus:ring-2 focus:ring-primary/50",
        selected && "border-primary bg-primary/5 ring-1 ring-primary/20",
        isDisabled && "cursor-not-allowed opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
            )}
          >
            <KindIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-sm">{agent.name}</span>
              <span className={cn("h-2 w-2 shrink-0 rounded-full", statusColor)} />
            </div>
            <div className="text-muted-foreground mt-0.5 text-xs">{getAgentKindLabel(agent.kind)}</div>
          </div>
        </div>

        {onConfigure && (
          <div
            className="opacity-0 transition-opacity group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(e) => {
                e.stopPropagation();
                onConfigure();
              }}
            >
              <Settings2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {/* Model & Capabilities */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {agent.default_model && (
          <Badge variant="outline" className="text-[10px]">
            {agent.default_model}
          </Badge>
        )}
        {agent.capabilities?.slice(0, 3).map((cap) => (
          <Badge key={cap} variant="secondary" className="text-[10px]">
            {cap}
          </Badge>
        ))}
        {(agent.capabilities?.length ?? 0) > 3 && (
          <Badge variant="secondary" className="text-[10px]">
            +{(agent.capabilities?.length ?? 0) - 3}
          </Badge>
        )}
      </div>

      {/* Status bar */}
      <div className="mt-3 flex items-center justify-between text-xs">
        <Badge
          variant={getAgentStatusBadgeVariant(agent.status)}
          className="text-[10px] capitalize"
        >
          {agent.status}
        </Badge>
        {agent.sandbox && (
          <span className="text-muted-foreground text-[10px]">sandbox: {agent.sandbox}</span>
        )}
      </div>
    </button>
  );
}

// =============================================================================
// AgentGrid Component
// =============================================================================

export function AgentGrid({
  projectId,
  selectedAgentId,
  onSelect,
  onConfigure,
  className,
  filterByCapability,
}: AgentGridProps) {
  const { data: agents, isLoading, error } = useAgents(projectId);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterKind, setFilterKind] = useState<string>("all");

  const { filteredAgents, kinds, groupedAgents } = useMemo(() => {
    if (!agents) return { filteredAgents: [], kinds: [], groupedAgents: {} };

    let filtered = filterByCapability
      ? filterAgentsByCapability(agents, filterByCapability)
      : agents;

    // Apply search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.kind.toLowerCase().includes(q) ||
          a.capabilities?.some((c) => c.toLowerCase().includes(q)),
      );
    }

    // Apply kind filter
    if (filterKind !== "all") {
      filtered = filtered.filter((a) => a.kind === filterKind);
    }

    filtered = sortAgentsByStatusAndName(filtered);
    const grouped = groupAgentsByKind(filtered);
    const kindKeys = Object.keys(grouped).sort();

    return { filteredAgents: filtered, kinds: kindKeys, groupedAgents: grouped };
  }, [agents, filterByCapability, searchQuery, filterKind]);

  const availableCount = filteredAgents.filter((a) => a.status === "available").length;

  if (isLoading) {
    return <LoadingState message="Loading agents..." />;
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Failed to load agents"
        description={error instanceof Error ? error.message : "An unknown error occurred"}
      />
    );
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Agents
            <Badge variant="secondary" className="text-xs">
              {availableCount}/{filteredAgents.length} available
            </Badge>
          </CardTitle>
        </div>

        {/* Search & Filter bar */}
        <div className="flex items-center gap-2 pt-2">
          <div className="relative flex-1">
            <Search className="text-muted-foreground absolute left-2.5 top-2.5 h-4 w-4" />
            <Input
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 pl-9 text-sm"
            />
          </div>
          <Select value={filterKind} onValueChange={setFilterKind}>
            <SelectTrigger className="h-9 w-[160px] text-sm">
              <SelectValue placeholder="Filter by kind" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Kinds</SelectItem>
              {kinds.map((kind) => (
                <SelectItem key={kind} value={kind}>
                  {getAgentKindLabel(kind)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {filteredAgents.length === 0 ? (
          <div className="text-muted-foreground py-8 text-center text-sm">
            {agents?.length === 0 ? "No agents configured" : "No agents match your filters"}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredAgents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                selected={agent.id === selectedAgentId}
                onSelect={() => onSelect(agent.id)}
                onConfigure={onConfigure ? () => onConfigure(agent.id) : undefined}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Select Variant (original dropdown)
// =============================================================================

export function AgentSelector({
  projectId,
  value,
  onChange,
  className,
  placeholder = "Select an agent",
  disabled = false,
  filterByCapability,
  showStatus = true,
  showModel = false,
}: AgentSelectorProps) {
  const { data: agents, isLoading, error } = useAgents(projectId);

  // Filter, sort, and group agents
  const { groupedAgents, availableCount } = useMemo(() => {
    if (!agents) return { groupedAgents: {}, availableCount: 0 };

    let filtered = filterByCapability
      ? filterAgentsByCapability(agents, filterByCapability)
      : agents;

    filtered = sortAgentsByStatusAndName(filtered);
    const grouped = groupAgentsByKind(filtered);
    const available = filtered.filter((a) => a.status === "available").length;

    return { groupedAgents: grouped, availableCount: available };
  }, [agents, filterByCapability]);

  if (isLoading) {
    return <LoadingState message="Loading agents..." />;
  }

  if (error) {
    return (
      <div className="text-destructive flex items-center gap-2 text-sm">
        <AlertCircle className="h-4 w-4" />
        Failed to load agents
      </div>
    );
  }

  const selectedAgent = agents?.find((a) => a.id === value);
  const kinds = Object.keys(groupedAgents).sort();

  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder}>
          {selectedAgent && (
            <div className="flex items-center gap-2">
              {showStatus && (
                <span
                  className={cn("h-2 w-2 rounded-full", getAgentStatusColor(selectedAgent.status))}
                />
              )}
              <span>{selectedAgent.name}</span>
              {showModel && selectedAgent.default_model && (
                <Badge variant="outline" className="ml-auto text-xs">
                  {selectedAgent.default_model}
                </Badge>
              )}
            </div>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel className="flex items-center justify-between">
            <span>Available Agents</span>
            <Badge variant="secondary" className="text-xs">
              {availableCount} available
            </Badge>
          </SelectLabel>
        </SelectGroup>
        <SelectSeparator />

        {kinds.length === 0 ? (
          <div className="text-muted-foreground p-4 text-center text-sm">No agents available</div>
        ) : (
          kinds.map((kind, index) => (
            <SelectGroup key={kind}>
              {index > 0 && <SelectSeparator />}
              <SelectLabel>{getAgentKindLabel(kind)}</SelectLabel>
              {groupedAgents[kind].map((agent) => (
                <SelectItem
                  key={agent.id}
                  value={agent.id}
                  disabled={agent.status === "unavailable"}
                >
                  <div className="flex w-full items-center gap-2">
                    {showStatus && (
                      <span
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full",
                          getAgentStatusColor(agent.status),
                        )}
                      />
                    )}
                    <span className="flex-1">{agent.name}</span>
                    {agent.capabilities && agent.capabilities.length > 0 && (
                      <Badge variant="outline" className="text-xs">
                        {agent.capabilities.length} caps
                      </Badge>
                    )}
                    {showModel && agent.default_model && (
                      <Badge variant="secondary" className="text-xs">
                        {agent.default_model}
                      </Badge>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectGroup>
          ))
        )}
      </SelectContent>
    </Select>
  );
}

// =============================================================================
// Compact Variant
// =============================================================================

export interface CompactAgentSelectorProps extends Omit<
  AgentSelectorProps,
  "showStatus" | "showModel"
> {
  /** Show inline status indicator */
  inline?: boolean;
}

/**
 * A more compact version of the agent selector for use in tight spaces
 */
export function CompactAgentSelector({
  projectId,
  value,
  onChange,
  className,
  placeholder = "Agent",
  disabled = false,
  filterByCapability,
  inline = true,
}: CompactAgentSelectorProps) {
  const { data: agents, isLoading } = useAgents(projectId);

  const filteredAgents = useMemo(() => {
    if (!agents) return [];
    const filtered = filterByCapability
      ? filterAgentsByCapability(agents, filterByCapability)
      : agents;
    return sortAgentsByStatusAndName(filtered);
  }, [agents, filterByCapability]);

  if (isLoading) {
    return (
      <Select disabled>
        <SelectTrigger className={cn("w-[180px]", className)}>
          <SelectValue placeholder="Loading..." />
        </SelectTrigger>
      </Select>
    );
  }

  const selectedAgent = agents?.find((a) => a.id === value);

  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className={cn("w-[180px]", className)} size="sm">
        <SelectValue placeholder={placeholder}>
          {selectedAgent && inline && (
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  getAgentStatusColor(selectedAgent.status),
                )}
              />
              <span className="truncate">{selectedAgent.name}</span>
            </div>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {filteredAgents.length === 0 ? (
          <div className="text-muted-foreground p-2 text-center text-sm">No agents</div>
        ) : (
          filteredAgents.map((agent) => (
            <SelectItem key={agent.id} value={agent.id} disabled={agent.status === "unavailable"}>
              <div className="flex items-center gap-2">
                <span
                  className={cn("h-1.5 w-1.5 rounded-full", getAgentStatusColor(agent.status))}
                />
                <span>{agent.name}</span>
              </div>
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}
