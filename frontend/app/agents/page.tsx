"use client"

import { useMemo, useState } from "react"
import {
  useAgents,
  useAgentAssignments,
  useAgentHealth,
  useAgentMetrics,
  useAgentPrompts,
  useProjects,
  useUpdateAgentConfig,
  useUpdateAgentAssignments,
  useUpdateAgentPrompt,
} from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Bot, Circle, Settings, Plus, Activity, TrendingUp, Zap, RefreshCw, Layers, Info } from "lucide-react"
import { toast } from "sonner"
import type { Agent, AgentAssignments, AgentPromptTemplate, AgentUpdate } from "@/lib/api/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

type AgentCard = Agent & {
  enabled: boolean
  healthStatus: "available" | "unavailable" | "unknown" | "disabled"
  healthDetail?: string
  activeSteps: number
  completedSteps: number
}

type AgentDraft = {
  id: string
  name: string
  kind: string
  enabled: boolean
  default_model: string
  command: string
  command_dir: string
  endpoint: string
  sandbox: string
  format: string
  capabilities: string
  timeout_seconds: string
  max_retries: string
}

type AssignmentDraft = {
  agent_id?: string
  prompt_id?: string
}

type AssignmentsDraft = Record<string, AssignmentDraft>

type PromptDraft = {
  id: string
  name: string
  path: string
  kind: string
  engine_id: string
  model: string
  tags: string
  enabled: boolean
  description: string
}

const processAssignments = [
  {
    key: "onboarding_discovery",
    label: "Onboarding & Discovery",
    description: "Onboarding setup and repository discovery prompts.",
  },
  {
    key: "specs",
    label: "Specs",
    description: "SpecKit planning prompts (specs, plans, tasks).",
  },
  {
    key: "planning",
    label: "Planning",
    description: "Protocol planning prompt (creates plan and steps).",
  },
  {
    key: "execution",
    label: "Execution",
    description: "Prepended to each step before execution.",
  },
  {
    key: "qa",
    label: "Validation / QA",
    description: "Quality gate prompt used for step review.",
  },
]

export default function AgentsPage() {
  const { data: projects } = useProjects()
  const [scopeProjectId, setScopeProjectId] = useState("global")
  const projectId = scopeProjectId === "global" ? undefined : Number(scopeProjectId)

  const { data: agentsData, isLoading: agentsLoading } = useAgents(projectId)
  const { data: assignmentsData } = useAgentAssignments(projectId)
  const { data: promptsData } = useAgentPrompts(projectId)
  const {
    data: healthData,
    refetch: refreshHealth,
    isFetching: isRefreshingHealth,
  } = useAgentHealth(projectId)
  const { data: metricsData } = useAgentMetrics(projectId)

  const updateAgent = useUpdateAgentConfig()
  const updateAssignments = useUpdateAgentAssignments()
  const updatePrompt = useUpdateAgentPrompt()

  const [selectedAgent, setSelectedAgent] = useState<AgentDraft | null>(null)
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<PromptDraft | null>(null)
  const [isPromptOpen, setIsPromptOpen] = useState(false)
  const [assignmentsDraft, setAssignmentsDraft] = useState<AssignmentsDraft>({})
  const [inheritGlobalOverride, setInheritGlobalOverride] = useState<boolean | null>(null)

  const healthById = useMemo(() => {
    return new Map((healthData || []).map((health) => [health.agent_id, health]))
  }, [healthData])

  const metricsById = useMemo(() => {
    return new Map((metricsData || []).map((metrics) => [metrics.agent_id, metrics]))
  }, [metricsData])

  const agents: AgentCard[] = useMemo(() => {
    return (agentsData || []).map((agent) => {
      const enabled = agent.enabled ?? agent.status !== "unavailable"
      const health = healthById.get(agent.id)
      let healthStatus: AgentCard["healthStatus"] = "unknown"
      let healthDetail: string | undefined
      if (!enabled) {
        healthStatus = "disabled"
      } else if (health) {
        healthStatus = health.available ? "available" : "unavailable"
        healthDetail = health.error || health.version || undefined
      } else if (agent.status === "available") {
        healthStatus = "available"
      }
      const metrics = metricsById.get(agent.id)
      return {
        ...agent,
        enabled,
        healthStatus,
        healthDetail,
        activeSteps: metrics?.active_steps || 0,
        completedSteps: metrics?.completed_steps || 0,
      }
    })
  }, [agentsData, healthById, metricsById])

  const baselineAssignments = useMemo<AssignmentsDraft>(() => {
    const nextDraft: AssignmentsDraft = {}
    processAssignments.forEach((process) => {
      const assignment = assignmentsData?.assignments?.[process.key]
      nextDraft[process.key] = {
        agent_id: assignment?.agent_id || "",
        prompt_id: assignment?.prompt_id || "",
      }
    })
    return nextDraft
  }, [assignmentsData])

  const effectiveAssignments = useMemo<AssignmentsDraft>(() => {
    const keys = new Set([...Object.keys(baselineAssignments), ...Object.keys(assignmentsDraft)])
    const merged: AssignmentsDraft = {}
    keys.forEach((key) => {
      const base = baselineAssignments[key] || {}
      const draft = assignmentsDraft[key] || {}
      merged[key] = {
        agent_id: draft.agent_id ?? base.agent_id ?? "",
        prompt_id: draft.prompt_id ?? base.prompt_id ?? "",
      }
    })
    return merged
  }, [assignmentsDraft, baselineAssignments])

  const statusColors = {
    available: { bg: "bg-green-500", text: "Available" },
    unavailable: { bg: "bg-red-500", text: "Unavailable" },
    disabled: { bg: "bg-slate-400", text: "Disabled" },
    unknown: { bg: "bg-amber-500", text: "Unknown" },
  }

  const stats = {
    total: agents.length,
    enabled: agents.filter((agent) => agent.enabled).length,
    available: agents.filter((agent) => agent.healthStatus === "available").length,
    activeSteps: agents.reduce((sum, agent) => sum + agent.activeSteps, 0),
    completedSteps: agents.reduce((sum, agent) => sum + agent.completedSteps, 0),
  }

  const inheritGlobal = inheritGlobalOverride ?? Boolean(assignmentsData?.inherit_global ?? true)
  const inheritEnabled = projectId ? inheritGlobal : true

  const promptOptions = promptsData || []
  const assignmentsReady = Boolean(assignmentsData)

  const handleScopeChange = (value: string) => {
    setScopeProjectId(value)
    setAssignmentsDraft({})
    setInheritGlobalOverride(null)
  }

  const handleToggleInheritance = (value: boolean) => {
    if (!projectId) return
    updateAssignments.mutate(
      {
        projectId,
        assignments: {
          assignments: {},
          inherit_global: value,
        },
      },
      {
        onSuccess: () => {
          setInheritGlobalOverride(value)
        },
        onError: (error) => {
          toast.error(error instanceof Error ? error.message : "Failed to update inheritance")
        },
      },
    )
  }

  if (agentsLoading) {
    return <LoadingState message="Loading agents..." />
  }

  if (!agents || agents.length === 0) {
    return (
      <div className="flex h-full flex-col gap-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Agents</h1>
            <p className="text-sm text-muted-foreground">Manage AI agents and their configurations</p>
          </div>
          <ScopeSelector
            projects={projects || []}
            value={scopeProjectId}
            onChange={handleScopeChange}
            showInheritance={!!projectId}
            inheritEnabled={inheritEnabled}
            onToggleInheritance={handleToggleInheritance}
          />
        </div>
        <EmptyState
          icon={Bot}
          title="No agents configured"
          description="Configure agents in your DevGodzilla setup to see them here."
        />
      </div>
    )
  }

  const openAgentConfig = (agent: AgentCard) => {
    setSelectedAgent({
      id: agent.id,
      name: agent.name,
      kind: agent.kind,
      enabled: agent.enabled,
      default_model: agent.default_model || "",
      command: agent.command || "",
      command_dir: agent.command_dir || "",
      endpoint: agent.endpoint || "",
      sandbox: agent.sandbox || "",
      format: agent.format || "",
      capabilities: agent.capabilities?.join(", ") || "",
      timeout_seconds: agent.timeout_seconds ? String(agent.timeout_seconds) : "",
      max_retries: agent.max_retries ? String(agent.max_retries) : "",
    })
    setIsConfigOpen(true)
  }

  const openPromptConfig = (prompt: AgentPromptTemplate) => {
    setSelectedPrompt({
      id: prompt.id,
      name: prompt.name,
      path: prompt.path,
      kind: prompt.kind || "",
      engine_id: prompt.engine_id || "",
      model: prompt.model || "",
      tags: prompt.tags?.join(", ") || "",
      enabled: prompt.enabled ?? true,
      description: prompt.description || "",
    })
    setIsPromptOpen(true)
  }

  const handleSaveAgent = async () => {
    if (!selectedAgent) return
    const toNullable = (value: string) => (value.trim().length > 0 ? value.trim() : null)
    const toNumber = (value: string) => (value.trim().length > 0 ? Number(value) : null)

    const payload: AgentUpdate = {
      name: toNullable(selectedAgent.name),
      kind: toNullable(selectedAgent.kind),
      enabled: selectedAgent.enabled,
      default_model: toNullable(selectedAgent.default_model),
      command: toNullable(selectedAgent.command),
      command_dir: toNullable(selectedAgent.command_dir),
      endpoint: toNullable(selectedAgent.endpoint),
      sandbox: toNullable(selectedAgent.sandbox),
      format: toNullable(selectedAgent.format),
      capabilities: selectedAgent.capabilities
        .split(",")
        .map((cap) => cap.trim())
        .filter(Boolean),
      timeout_seconds: toNumber(selectedAgent.timeout_seconds),
      max_retries: toNumber(selectedAgent.max_retries),
    }

    try {
      await updateAgent.mutateAsync({
        agentId: selectedAgent.id,
        data: payload,
        projectId,
      })
      toast.success("Agent updated")
      setIsConfigOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update agent")
    }
  }

  const handleSaveAssignments = async () => {
    const toNullable = (value: string) => (value.trim().length > 0 ? value.trim() : null)
    const baseline = assignmentsData?.assignments || {}
    const assignments = Object.fromEntries(
      processAssignments.flatMap((process) => {
        const draft = effectiveAssignments[process.key] || { agent_id: "", prompt_id: "" }
        const nextAgent = toNullable(draft.agent_id ?? "")
        const nextPrompt = toNullable(draft.prompt_id ?? "")
        const currentAgent = toNullable(baseline[process.key]?.agent_id || "")
        const currentPrompt = toNullable(baseline[process.key]?.prompt_id || "")
        if (nextAgent === currentAgent && nextPrompt === currentPrompt) {
          return []
        }
        return [
          [
            process.key,
            {
              agent_id: nextAgent,
              prompt_id: nextPrompt,
            },
          ],
        ]
      }),
    )
    const payload: AgentAssignments = {
      assignments,
      inherit_global: projectId ? inheritGlobal : undefined,
    }

    try {
      await updateAssignments.mutateAsync({
        projectId,
        assignments: payload,
      })
      toast.success("Assignments updated")
      setAssignmentsDraft({})
      setInheritGlobalOverride(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update assignments")
    }
  }

  const handleSavePrompt = async () => {
    if (!selectedPrompt) return
    const toNullable = (value: string) => (value.trim().length > 0 ? value.trim() : null)
    const payload = {
      name: toNullable(selectedPrompt.name),
      path: toNullable(selectedPrompt.path),
      kind: toNullable(selectedPrompt.kind),
      engine_id: toNullable(selectedPrompt.engine_id),
      model: toNullable(selectedPrompt.model),
      tags: selectedPrompt.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      enabled: selectedPrompt.enabled,
      description: toNullable(selectedPrompt.description),
    }

    try {
      await updatePrompt.mutateAsync({
        projectId,
        promptId: selectedPrompt.id,
        data: payload,
      })
      toast.success("Prompt template updated")
      setIsPromptOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update prompt")
    }
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground">Manage AI agents, prompt templates, and assignments</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ScopeSelector
            projects={projects || []}
            value={scopeProjectId}
            onChange={handleScopeChange}
            showInheritance={!!projectId}
            inheritEnabled={inheritEnabled}
            onToggleInheritance={handleToggleInheritance}
          />
          <Button variant="outline" size="sm" onClick={() => refreshHealth()} disabled={isRefreshingHealth}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {isRefreshingHealth ? "Refreshing" : "Refresh Health"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="agents" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="prompts">Prompts</TabsTrigger>
        </TabsList>

        <TabsContent value="agents" className="space-y-6 mt-4">
          <div className="bg-muted/50 border rounded-lg p-4">
            <div className="flex flex-wrap items-center justify-between gap-6">
              <StatBlock label="Total Agents" value={stats.total} icon={Bot} iconClass="text-blue-500" />
              <Divider />
              <StatBlock label="Enabled" value={stats.enabled} icon={Circle} iconClass="text-green-500" />
              <Divider />
              <StatBlock label="Available" value={stats.available} icon={Activity} iconClass="text-green-500" />
              <Divider />
              <StatBlock label="Active Steps" value={stats.activeSteps} icon={Zap} iconClass="text-amber-500" />
              <Divider />
              <StatBlock label="Completed" value={stats.completedSteps} icon={TrendingUp} iconClass="text-cyan-500" />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agents.map((agent) => (
              <Card key={agent.id} className="relative overflow-hidden hover:shadow-lg transition-shadow">
                <div className={`absolute left-0 top-0 h-full w-1 ${statusColors[agent.healthStatus].bg}`} />
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Bot className="h-5 w-5 text-blue-500" />
                      <CardTitle className="text-base">{agent.name}</CardTitle>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Circle
                        className={`h-2 w-2 fill-current ${statusColors[agent.healthStatus].bg.replace("bg-", "text-")}`}
                      />
                      <span className="text-xs text-muted-foreground">{statusColors[agent.healthStatus].text}</span>
                    </div>
                  </div>
                  <CardDescription className="text-xs">{agent.kind}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model</span>
                      <span className="font-mono text-xs truncate max-w-[140px]">{agent.default_model || "-"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Command / Endpoint</span>
                      <span className="text-xs truncate max-w-[140px]">
                        {agent.command || agent.endpoint || "-"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Active Steps</span>
                      <Badge variant={agent.activeSteps > 0 ? "default" : "secondary"} className="text-xs">
                        {agent.activeSteps}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Capabilities</span>
                      <span className="text-xs">{agent.capabilities?.length || 0}</span>
                    </div>
                    {agent.healthDetail && (
                      <p className="text-xs text-muted-foreground truncate">{agent.healthDetail}</p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full bg-transparent"
                    onClick={() => openAgentConfig(agent)}
                  >
                    <Settings className="mr-2 h-3 w-3" />
                    Configure
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="assignments" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Process Agent Assignments</CardTitle>
              <CardDescription>Set default agents for each workflow process.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                {processAssignments.map((process) => (
                  <AssignmentSelect
                    key={process.key}
                    label={process.label}
                    value={effectiveAssignments[process.key]?.agent_id || ""}
                    agents={agents}
                    onChange={(value) =>
                      setAssignmentsDraft((prev) => ({
                        ...prev,
                        [process.key]: { ...prev[process.key], agent_id: value },
                      }))
                    }
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Prompt Assignments</CardTitle>
              <CardDescription>Map prompts to each workflow process.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                {processAssignments.map((assignment) => (
                  <PromptAssignmentSelect
                    key={assignment.key}
                    label={assignment.label}
                    description={assignment.description}
                    value={effectiveAssignments[assignment.key]?.prompt_id || ""}
                    prompts={promptOptions}
                    onChange={(value) =>
                      setAssignmentsDraft((prev) => ({
                        ...prev,
                        [assignment.key]: { ...prev[assignment.key], prompt_id: value },
                      }))
                    }
                  />
                ))}
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSaveAssignments} disabled={updateAssignments.isPending || !assignmentsReady}>
                  Save Assignments
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prompts" className="space-y-6 mt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Prompt Templates</h2>
              <p className="text-sm text-muted-foreground">Edit reusable prompts and per-project overrides.</p>
            </div>
            <Button
              size="sm"
              onClick={() =>
                openPromptConfig({
                  id: "new-prompt",
                  name: "New Prompt",
                  path: "prompts/",
                  enabled: true,
                } as AgentPromptTemplate)
              }
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Prompt
            </Button>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {promptOptions.length === 0 ? (
              <EmptyState
                icon={Layers}
                title="No prompt templates"
                description="Create a prompt template to assign it to workflows."
              />
            ) : (
              promptOptions.map((prompt) => (
                <Card key={prompt.id} className="relative">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="text-base">{prompt.name}</CardTitle>
                        <CardDescription className="text-xs">{prompt.id}</CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {prompt.source === "project" && <Badge variant="secondary">Project</Badge>}
                        {prompt.enabled === false && <Badge variant="outline">Disabled</Badge>}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Path</span>
                      <span className="text-xs truncate max-w-[180px]">{prompt.path}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Engine</span>
                      <span className="text-xs">{prompt.engine_id || "-"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model</span>
                      <span className="text-xs">{prompt.model || "-"}</span>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => openPromptConfig(prompt)}>
                      Edit Prompt
                    </Button>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={isConfigOpen} onOpenChange={setIsConfigOpen}>
        <DialogContent size="2xl" className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-500" />
              Configure {selectedAgent?.name}
            </DialogTitle>
            <DialogDescription>
              {projectId ? "Editing project-level overrides" : "Editing global agent configuration"}
            </DialogDescription>
          </DialogHeader>

          {selectedAgent && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="agent-name">Agent Name</Label>
                  <Input
                    id="agent-name"
                    value={selectedAgent.name}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, name: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-kind">Agent Kind</Label>
                  <Input
                    id="agent-kind"
                    value={selectedAgent.kind}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, kind: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="agent-command">Command</Label>
                  <Input
                    id="agent-command"
                    value={selectedAgent.command}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, command: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-endpoint">Endpoint</Label>
                  <Input
                    id="agent-endpoint"
                    value={selectedAgent.endpoint}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, endpoint: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="agent-default-model">Default Model</Label>
                  <Input
                    id="agent-default-model"
                    value={selectedAgent.default_model}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, default_model: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-command-dir">Command Dir</Label>
                  <Input
                    id="agent-command-dir"
                    value={selectedAgent.command_dir}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, command_dir: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="agent-sandbox">Sandbox</Label>
                  <Input
                    id="agent-sandbox"
                    value={selectedAgent.sandbox}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, sandbox: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-format">Format</Label>
                  <Input
                    id="agent-format"
                    value={selectedAgent.format}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, format: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="agent-timeout">Timeout (seconds)</Label>
                  <Input
                    id="agent-timeout"
                    type="number"
                    value={selectedAgent.timeout_seconds}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, timeout_seconds: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-retries">Max Retries</Label>
                  <Input
                    id="agent-retries"
                    type="number"
                    value={selectedAgent.max_retries}
                    onChange={(event) =>
                      setSelectedAgent((prev) => (prev ? { ...prev, max_retries: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agent-capabilities">Capabilities</Label>
                <Textarea
                  id="agent-capabilities"
                  rows={3}
                  value={selectedAgent.capabilities}
                  onChange={(event) =>
                    setSelectedAgent((prev) => (prev ? { ...prev, capabilities: event.target.value } : prev))
                  }
                  placeholder="code_gen, code_review"
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>Enabled</Label>
                  <p className="text-xs text-muted-foreground">Disable to prevent assignment.</p>
                </div>
                <Switch
                  checked={selectedAgent.enabled}
                  onCheckedChange={(value) =>
                    setSelectedAgent((prev) => (prev ? { ...prev, enabled: value } : prev))
                  }
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setIsConfigOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveAgent} disabled={updateAgent.isPending}>
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPromptOpen} onOpenChange={setIsPromptOpen}>
        <DialogContent size="2xl" className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-blue-500" />
              {selectedPrompt?.name || "Prompt"}
            </DialogTitle>
            <DialogDescription>
              {projectId ? "Editing project-level prompt" : "Editing global prompt template"}
            </DialogDescription>
          </DialogHeader>

          {selectedPrompt && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="prompt-id">Prompt ID</Label>
                  <Input
                    id="prompt-id"
                    value={selectedPrompt.id}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, id: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prompt-name">Prompt Name</Label>
                  <Input
                    id="prompt-name"
                    value={selectedPrompt.name}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, name: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="prompt-path">Prompt Path</Label>
                <Input
                  id="prompt-path"
                  value={selectedPrompt.path}
                  onChange={(event) =>
                    setSelectedPrompt((prev) => (prev ? { ...prev, path: event.target.value } : prev))
                  }
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="prompt-kind">Kind</Label>
                  <Input
                    id="prompt-kind"
                    value={selectedPrompt.kind}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, kind: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prompt-engine">Engine</Label>
                  <Input
                    id="prompt-engine"
                    value={selectedPrompt.engine_id}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, engine_id: event.target.value } : prev))
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="prompt-model">Model</Label>
                  <Input
                    id="prompt-model"
                    value={selectedPrompt.model}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, model: event.target.value } : prev))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prompt-tags">Tags</Label>
                  <Input
                    id="prompt-tags"
                    value={selectedPrompt.tags}
                    onChange={(event) =>
                      setSelectedPrompt((prev) => (prev ? { ...prev, tags: event.target.value } : prev))
                    }
                    placeholder="planning, qa"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="prompt-description">Description</Label>
                <Textarea
                  id="prompt-description"
                  rows={3}
                  value={selectedPrompt.description}
                  onChange={(event) =>
                    setSelectedPrompt((prev) => (prev ? { ...prev, description: event.target.value } : prev))
                  }
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>Enabled</Label>
                  <p className="text-xs text-muted-foreground">Disable to hide from assignments.</p>
                </div>
                <Switch
                  checked={selectedPrompt.enabled}
                  onCheckedChange={(value) =>
                    setSelectedPrompt((prev) => (prev ? { ...prev, enabled: value } : prev))
                  }
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setIsPromptOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSavePrompt} disabled={updatePrompt.isPending}>
              Save Prompt
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ScopeSelector({
  projects,
  value,
  onChange,
  showInheritance,
  inheritEnabled,
  onToggleInheritance,
}: {
  projects: Array<{ id: number; name: string }>
  value: string
  onChange: (value: string) => void
  showInheritance: boolean
  inheritEnabled: boolean
  onToggleInheritance: (value: boolean) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-52">
          <SelectValue placeholder="Scope" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="global">Global Defaults</SelectItem>
          {projects.map((project) => (
            <SelectItem key={project.id} value={String(project.id)}>
              {project.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {showInheritance && (
        <div className="flex items-center gap-2 rounded-md border px-3 py-2">
          <Label className="text-xs">Inherit Global</Label>
          <Switch checked={inheritEnabled} onCheckedChange={onToggleInheritance} />
        </div>
      )}
    </div>
  )
}

function StatBlock({
  label,
  value,
  icon: Icon,
  iconClass,
}: {
  label: string
  value: number
  icon: typeof Bot
  iconClass: string
}) {
  return (
    <div className="flex items-center gap-2">
      <div className={`h-8 w-8 rounded-md bg-muted flex items-center justify-center ${iconClass}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <div className="text-sm font-medium text-muted-foreground">{label}</div>
        <div className="text-2xl font-bold">{value}</div>
      </div>
    </div>
  )
}

function Divider() {
  return <div className="h-12 w-px bg-border hidden md:block" />
}

function AssignmentSelect({
  label,
  value,
  agents,
  onChange,
}: {
  label: string
  value: string
  agents: AgentCard[]
  onChange: (value: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select agent" />
        </SelectTrigger>
        <SelectContent>
          {agents.map((agent) => (
            <SelectItem key={agent.id} value={agent.id}>
              {agent.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function PromptAssignmentSelect({
  label,
  value,
  prompts,
  onChange,
  description,
}: {
  label: string
  value: string
  prompts: AgentPromptTemplate[]
  onChange: (value: string) => void
  description?: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label>{label}</Label>
        {description && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="rounded-full p-1 text-muted-foreground transition-colors hover:text-foreground"
                aria-label={`${label} help`}
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[240px]">
              {description}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select prompt" />
        </SelectTrigger>
        <SelectContent>
          {prompts.map((prompt) => (
            <SelectItem key={prompt.id} value={prompt.id}>
              {prompt.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
