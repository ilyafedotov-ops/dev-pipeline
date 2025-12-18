"use client"

import { useState } from "react"
import { useAgents } from "@/lib/api"
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
import { Bot, Circle, Settings, Plus, Activity, TrendingUp, Zap } from "lucide-react"
import type { Agent } from "@/lib/api/types"

type AgentConfig = Agent & {
  activeJobs?: number
  completedJobs?: number
  avgResponseTime?: string
  maxConcurrency?: number
  temperature?: number
  maxTokens?: number
  systemPrompt?: string
}

export default function AgentsPage() {
  const { data: agentsData, isLoading } = useAgents()
  const [selectedAgent, setSelectedAgent] = useState<AgentConfig | null>(null)
  const [isConfigOpen, setIsConfigOpen] = useState(false)

  // Transform API data to include display fields
  const agents: AgentConfig[] = (agentsData || []).map((agent) => ({
    ...agent,
    status: agent.status || "available",
    activeJobs: 0,
    completedJobs: 0,
    avgResponseTime: "-",
    maxConcurrency: 5,
    temperature: 0.7,
    maxTokens: 4096,
  }))

  const statusColors = {
    available: { bg: "bg-green-500", text: "Available" },
    busy: { bg: "bg-amber-500", text: "Busy" },
    unavailable: { bg: "bg-red-500", text: "Unavailable" },
  }

  const stats = {
    total: agents.length,
    available: agents.filter((a) => a.status === "available").length,
    busy: agents.filter((a) => a.status === "busy").length,
    totalActiveJobs: agents.reduce((sum, a) => sum + (a.activeJobs || 0), 0),
    totalCompleted: agents.reduce((sum, a) => sum + (a.completedJobs || 0), 0),
  }

  if (isLoading) {
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
          <Button size="sm">
            <Plus className="mr-2 h-4 w-4" />
            Add Agent
          </Button>
        </div>
        <EmptyState
          icon={Bot}
          title="No agents configured"
          description="Configure agents in your DevGodzilla setup to see them here."
        />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground">Manage AI agents and their configurations</p>
        </div>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Add Agent
        </Button>
      </div>

      <div className="bg-muted/50 border rounded-lg p-4">
        <div className="flex items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-blue-500/10 flex items-center justify-center">
              <Bot className="h-4 w-4 text-blue-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Total Agents</div>
              <div className="text-2xl font-bold">{stats.total}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-green-500/10 flex items-center justify-center">
              <Circle className="h-4 w-4 text-green-500 fill-green-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Available</div>
              <div className="text-2xl font-bold">{stats.available}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-amber-500/10 flex items-center justify-center">
              <Activity className="h-4 w-4 text-amber-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Busy</div>
              <div className="text-2xl font-bold">{stats.busy}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-purple-500/10 flex items-center justify-center">
              <Zap className="h-4 w-4 text-purple-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Active Jobs</div>
              <div className="text-2xl font-bold">{stats.totalActiveJobs}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-cyan-500/10 flex items-center justify-center">
              <TrendingUp className="h-4 w-4 text-cyan-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Completed</div>
              <div className="text-2xl font-bold">{stats.totalCompleted}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {agents.map((agent) => (
          <Card key={agent.id} className="relative overflow-hidden hover:shadow-lg transition-shadow">
            <div className={`absolute left-0 top-0 h-full w-1 ${statusColors[agent.status].bg}`} />
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-blue-500" />
                  <CardTitle className="text-base">{agent.name}</CardTitle>
                </div>
                <div className="flex items-center gap-1.5">
                  <Circle className={`h-2 w-2 fill-current ${statusColors[agent.status].bg.replace("bg-", "text-")}`} />
                  <span className="text-xs text-muted-foreground">{statusColors[agent.status].text}</span>
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
                  <span className="text-muted-foreground">Active Jobs</span>
                  <Badge variant={(agent.activeJobs || 0) > 0 ? "default" : "secondary"} className="text-xs">
                    {agent.activeJobs || 0}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Capabilities</span>
                  <span className="text-xs">{agent.capabilities?.length || 0}</span>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full bg-transparent"
                onClick={() => {
                  setSelectedAgent(agent)
                  setIsConfigOpen(true)
                }}
              >
                <Settings className="mr-2 h-3 w-3" />
                Configure
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={isConfigOpen} onOpenChange={setIsConfigOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-500" />
              Configure {selectedAgent?.name}
            </DialogTitle>
            <DialogDescription>Adjust agent settings and parameters</DialogDescription>
          </DialogHeader>

          {selectedAgent && (
            <Tabs defaultValue="general" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="general">General</TabsTrigger>
                <TabsTrigger value="model">Model</TabsTrigger>
                <TabsTrigger value="performance">Performance</TabsTrigger>
              </TabsList>

              <TabsContent value="general" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="agent-name">Agent Name</Label>
                  <Input id="agent-name" defaultValue={selectedAgent.name} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-kind">Agent Kind</Label>
                  <Input id="agent-kind" defaultValue={selectedAgent.kind} disabled />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-status">Status</Label>
                  <Select defaultValue={selectedAgent.status}>
                    <SelectTrigger id="agent-status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="available">Available</SelectItem>
                      <SelectItem value="busy">Busy</SelectItem>
                      <SelectItem value="unavailable">Unavailable</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Enable Auto-scaling</Label>
                    <p className="text-xs text-muted-foreground">Automatically adjust capacity based on load</p>
                  </div>
                  <Switch />
                </div>
              </TabsContent>

              <TabsContent value="model" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Input id="model" defaultValue={selectedAgent.default_model || ""} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="temperature">Temperature: {selectedAgent.temperature}</Label>
                  <Input
                    id="temperature"
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    defaultValue={selectedAgent.temperature}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">Controls randomness in responses</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-tokens">Max Tokens</Label>
                  <Input id="max-tokens" type="number" defaultValue={selectedAgent.maxTokens} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="system-prompt">System Prompt</Label>
                  <Textarea
                    id="system-prompt"
                    rows={4}
                    defaultValue={selectedAgent.systemPrompt || ""}
                    placeholder="Enter system prompt..."
                  />
                </div>
              </TabsContent>

              <TabsContent value="performance" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="max-concurrency">Max Concurrency</Label>
                  <Input id="max-concurrency" type="number" defaultValue={selectedAgent.maxConcurrency} />
                  <p className="text-xs text-muted-foreground">Maximum parallel job executions</p>
                </div>
                <div className="space-y-4 rounded-lg border p-4 bg-muted/50">
                  <h4 className="font-medium flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Current Metrics
                  </h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Active Jobs</p>
                      <p className="text-2xl font-bold">{selectedAgent.activeJobs || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Completed Jobs</p>
                      <p className="text-2xl font-bold">{selectedAgent.completedJobs || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Avg Response Time</p>
                      <p className="text-2xl font-bold">{selectedAgent.avgResponseTime || "-"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Success Rate</p>
                      <p className="text-2xl font-bold">-</p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Enable Rate Limiting</Label>
                    <p className="text-xs text-muted-foreground">Prevent API quota exhaustion</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </TabsContent>
            </Tabs>
          )}

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setIsConfigOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setIsConfigOpen(false)}>Save Changes</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
