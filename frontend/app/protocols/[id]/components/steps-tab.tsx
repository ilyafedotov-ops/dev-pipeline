"use client"

import Link from "next/link"
import { useProtocolSteps, useStepAction } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { StatusPill } from "@/components/ui/status-pill"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Play, ClipboardCheck, CheckCircle, ExternalLink, ListChecks } from "lucide-react"
import { toast } from "sonner"
import type { ColumnDef } from "@tanstack/react-table"
import type { StepRun } from "@/lib/api/types"

interface StepsTabProps {
  protocolId: number
}

export function StepsTab({ protocolId }: StepsTabProps) {
  const { data: steps, isLoading } = useProtocolSteps(protocolId)
  const stepAction = useStepAction()

  const handleAction = async (stepId: number, action: "run" | "run_qa" | "approve") => {
    try {
      const result = await stepAction.mutateAsync({ stepId, protocolId, action })
      toast.success(result.message || `Action ${action} executed`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`)
    }
  }

  const columns: ColumnDef<StepRun>[] = [
    {
      accessorKey: "step_index",
      header: "Idx",
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.step_index}</span>,
    },
    {
      accessorKey: "step_name",
      header: "Name",
      cell: ({ row }) => (
        <Link href={`/steps/${row.original.id}`} className="font-medium hover:underline">
          {row.original.step_name}
        </Link>
      ),
    },
    {
      accessorKey: "step_type",
      header: "Type",
      cell: ({ row }) => <span className="capitalize text-muted-foreground">{row.original.step_type}</span>,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusPill status={row.original.status} size="sm" />,
    },
    {
      accessorKey: "engine_id",
      header: "Engine",
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.engine_id || "-"}</span>,
    },
    {
      accessorKey: "retries",
      header: "Retries",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.retries}</span>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const step = row.original
        const canRun = step.status === "pending"
        const canRunQA = step.status === "completed" || step.status === "needs_qa"
        const canApprove = step.status === "needs_qa"

        return (
          <div className="flex gap-1">
            {canRun && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  handleAction(step.id, "run")
                }}
                disabled={stepAction.isPending}
              >
                <Play className="h-4 w-4" />
              </Button>
            )}
            {canRunQA && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  handleAction(step.id, "run_qa")
                }}
                disabled={stepAction.isPending}
              >
                <ClipboardCheck className="h-4 w-4" />
              </Button>
            )}
            {canApprove && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  handleAction(step.id, "approve")
                }}
                disabled={stepAction.isPending}
              >
                <CheckCircle className="h-4 w-4" />
              </Button>
            )}
            <Link href={`/steps/${step.id}`}>
              <Button variant="ghost" size="sm">
                <ExternalLink className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        )
      },
    },
  ]

  if (isLoading) return <LoadingState message="Loading steps..." />

  if (!steps || steps.length === 0) {
    return <EmptyState icon={ListChecks} title="No steps yet" description="This protocol has no steps defined yet." />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Steps</h3>
          <p className="text-sm text-muted-foreground">
            {steps.filter((s) => s.status === "completed").length} / {steps.length} completed
          </p>
        </div>
      </div>
      <DataTable columns={columns} data={steps} />
    </div>
  )
}
