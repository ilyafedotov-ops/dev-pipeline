"use client"
import { use } from "react"

import Link from "next/link"
import { useProtocolSteps, useStepRuns, useStepPolicyFindings, useStepAction, useProtocol } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DataTable } from "@/components/ui/data-table"
import { StatusPill } from "@/components/ui/status-pill"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { CodeBlock } from "@/components/ui/code-block"
import { ArrowLeft, Play, ClipboardCheck, CheckCircle, ExternalLink, PlayCircle, AlertTriangle } from "lucide-react"
import { toast } from "sonner"
import { formatRelativeTime, truncateHash } from "@/lib/format"
import type { ColumnDef } from "@tanstack/react-table"
import type { CodexRun, StepRun, PolicyFinding } from "@/lib/api/types"

export default function StepDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const stepId = Number.parseInt(id, 10)

  // We need to find the step within protocol steps
  // First, get the step runs to find the protocol_run_id
  const { data: runs, isLoading: runsLoading } = useStepRuns(stepId)

  // Get the protocol_run_id from the first run or URL param
  const protocolRunId = runs?.[0]?.protocol_run_id

  const { data: protocol } = useProtocol(protocolRunId)
  const { data: steps } = useProtocolSteps(protocolRunId)
  const { data: findings } = useStepPolicyFindings(stepId)
  const stepAction = useStepAction()

  const step = steps?.find((s) => s.id === stepId)

  if (runsLoading && !step) return <LoadingState message="Loading step..." />

  // If we can't find the step, show basic view with runs
  const displayStep =
    step ||
    ({
      id: stepId,
      step_name: `Step ${stepId}`,
      step_type: "unknown",
      status: "pending",
      step_index: 0,
      retries: 0,
      protocol_run_id: protocolRunId || 0,
    } as StepRun)

  const handleAction = async (action: "run" | "run_qa" | "approve") => {
    if (!protocolRunId) return
    try {
      const result = await stepAction.mutateAsync({
        stepId,
        protocolId: protocolRunId,
        action,
      })
      toast.success(result.message || `Action ${action} executed`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`)
    }
  }

  const canRun = displayStep.status === "pending"
  const canRunQA = displayStep.status === "completed" || displayStep.status === "needs_qa"
  const canApprove = displayStep.status === "needs_qa"

  return (
    <div className="container py-8">
      <div className="mb-6">
        {protocol && (
          <Link
            href={`/protocols/${protocol.id}`}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to {protocol.protocol_name}
          </Link>
        )}

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              {displayStep.step_name}
              <StatusPill status={displayStep.status} />
            </h1>
            <p className="text-muted-foreground flex items-center gap-2 mt-1">
              <span>Index: {displayStep.step_index}</span>
              <span className="text-muted-foreground">•</span>
              <span className="capitalize">Type: {displayStep.step_type}</span>
              {displayStep.engine_id && (
                <>
                  <span className="text-muted-foreground">•</span>
                  <span>Engine: {displayStep.engine_id}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex gap-2">
            {canRun && (
              <Button onClick={() => handleAction("run")} disabled={stepAction.isPending}>
                <Play className="mr-2 h-4 w-4" />
                Run
              </Button>
            )}
            {canRunQA && (
              <Button variant="secondary" onClick={() => handleAction("run_qa")} disabled={stepAction.isPending}>
                <ClipboardCheck className="mr-2 h-4 w-4" />
                Run QA
              </Button>
            )}
            {canApprove && (
              <Button variant="default" onClick={() => handleAction("approve")} disabled={stepAction.isPending}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Approve
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
          </CardHeader>
          <CardContent>
            <StatusPill status={displayStep.status} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Retries</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{displayStep.retries}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Model</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{displayStep.model || "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Engine</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{displayStep.engine_id || "-"}</p>
          </CardContent>
        </Card>
      </div>

      {displayStep.runtime_state && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Runtime State</CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock code={displayStep.runtime_state} maxHeight="200px" />
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="runs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="policy">
            Policy Findings
            {findings && findings.length > 0 && (
              <span className="ml-1 rounded-full bg-yellow-500/10 px-2 text-xs text-yellow-500">{findings.length}</span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
          <StepRunsTab stepId={stepId} runs={runs} isLoading={runsLoading} />
        </TabsContent>
        <TabsContent value="policy">
          <StepPolicyTab findings={findings} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function StepRunsTab({
  stepId,
  runs,
  isLoading,
}: {
  stepId: number
  runs: CodexRun[] | undefined
  isLoading: boolean
}) {
  const columns: ColumnDef<CodexRun>[] = [
    {
      accessorKey: "run_id",
      header: "Run ID",
      cell: ({ row }) => (
        <Link href={`/runs/${row.original.run_id}`} className="font-mono text-sm hover:underline">
          {truncateHash(row.original.run_id, 12)}
        </Link>
      ),
    },
    {
      accessorKey: "run_kind",
      header: "Kind",
      cell: ({ row }) => <span className="capitalize">{row.original.run_kind}</span>,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusPill status={row.original.status} size="sm" />,
    },
    {
      accessorKey: "attempt",
      header: "Attempt",
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => <span className="text-muted-foreground">{formatRelativeTime(row.original.created_at)}</span>,
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Link href={`/runs/${row.original.run_id}`}>
            <Button variant="ghost" size="sm">
              <ExternalLink className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      ),
    },
  ]

  if (isLoading) return <LoadingState message="Loading runs..." />

  if (!runs || runs.length === 0) {
    return <EmptyState icon={PlayCircle} title="No runs yet" description="Execution runs will appear here." />
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Step Runs</h3>
        <p className="text-sm text-muted-foreground">{runs.length} run(s)</p>
      </div>
      <DataTable columns={columns} data={runs} />
    </div>
  )
}

function StepPolicyTab({ findings }: { findings: PolicyFinding[] | undefined }) {
  if (!findings || findings.length === 0) {
    return <EmptyState icon={AlertTriangle} title="No findings" description="No policy findings for this step." />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Policy Findings</CardTitle>
        <CardDescription>{findings.length} finding(s)</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {findings.map((finding, index) => (
            <div key={index} className="flex items-start gap-3 rounded-lg border p-3">
              <AlertTriangle
                className={`h-5 w-5 mt-0.5 ${finding.severity === "error" ? "text-destructive" : "text-yellow-500"}`}
              />
              <div className="flex-1 min-w-0">
                <p className="font-mono text-sm text-muted-foreground">{finding.code}</p>
                <p className="mt-1">{finding.message}</p>
                {finding.suggested_fix && (
                  <p className="text-sm text-muted-foreground mt-1">Suggested fix: {finding.suggested_fix}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
