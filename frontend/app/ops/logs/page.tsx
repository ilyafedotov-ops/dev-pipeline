"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import { useProjects, useRuns } from "@/lib/api"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ExternalLink, Activity } from "lucide-react"
import { LogsConsole } from "@/components/features/logs-console"
import { StreamingLogs } from "@/components/features/streaming-logs"

export default function LogsPage() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>(undefined)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const { data: projects } = useProjects()
  const { data: runs, isLoading: runsLoading } = useRuns({
    project_id: selectedProjectId,
    limit: 50,
  })

  const selectedRun = useMemo(() => runs?.find((run) => run.run_id === selectedRunId), [runs, selectedRunId])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">System Logs</h2>
          <p className="text-sm text-muted-foreground">Application and execution logs</p>
        </div>
      </div>

      <Tabs defaultValue="application" className="space-y-6">
        <TabsList>
          <TabsTrigger value="all-runs">All Runs</TabsTrigger>
          <TabsTrigger value="application">Application</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
        </TabsList>

        <TabsContent value="all-runs" className="space-y-6">
          <div className="flex flex-wrap items-center gap-4">
            <Select
              value={selectedProjectId?.toString() || "all"}
              onValueChange={(v) => {
                setSelectedProjectId(v === "all" ? undefined : Number(v))
                setSelectedRunId(null)
              }}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="All Projects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Projects</SelectItem>
                {projects?.map((project) => (
                  <SelectItem key={project.id} value={project.id.toString()}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedRunId || ""} onValueChange={(value) => setSelectedRunId(value)}>
              <SelectTrigger className="w-72">
                <SelectValue placeholder="Select a run" />
              </SelectTrigger>
              <SelectContent>
                {runs?.map((run) => (
                  <SelectItem key={run.run_id} value={run.run_id}>
                    {run.job_type} - {run.status} - {run.run_id.slice(0, 8)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selectedRun && (
              <Link href={`/runs/${selectedRun.run_id}`} className="inline-flex items-center">
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Run Details
                </Button>
              </Link>
            )}
          </div>

          {runsLoading ? (
            <LoadingState message="Loading runs..." />
          ) : !runs || runs.length === 0 ? (
            <EmptyState icon={Activity} title="No runs" description="No runs available for log streaming." />
          ) : selectedRunId ? (
            <div className="h-[calc(100vh-24rem)]">
              <StreamingLogs runId={selectedRunId} />
            </div>
          ) : (
            <EmptyState icon={Activity} title="Select a run" description="Select a run from the dropdown to view its logs." />
          )}
        </TabsContent>

        <TabsContent value="application" className="space-y-6">
          <LogsConsole mode="application" />
        </TabsContent>

        <TabsContent value="agents" className="space-y-6">
          <LogsConsole mode="application" sourceFilter="devgodzilla.engines" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
