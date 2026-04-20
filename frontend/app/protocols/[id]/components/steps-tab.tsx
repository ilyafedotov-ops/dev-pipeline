"use client";

import { useState } from "react";
import Link from "next/link";

import type { ColumnDef } from "@tanstack/react-table";
import { AlertCircle,AlertTriangle, Bot,ClipboardCheck, ExternalLink, ListChecks, Play } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPill } from "@/components/ui/status-pill";
import {
  useAgents,
  useAssignStepAgent,
  useProtocol,
  useProtocolSteps,
  useStepAction,
} from "@/lib/api";
import type { StepRun } from "@/lib/api/types";

interface StepsTabProps {
  protocolId: number;
}

export function StepsTab({ protocolId }: StepsTabProps) {
  const { data: steps, isLoading } = useProtocolSteps(protocolId);
  const { data: protocol } = useProtocol(protocolId);
  const { data: agents } = useAgents(protocol?.project_id);
  const stepAction = useStepAction();
  const assignAgent = useAssignStepAgent();
  const [assignStep, setAssignStep] = useState<StepRun | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState("");

  const handleAction = async (stepId: number, action: "execute" | "qa") => {
    try {
      const result = await stepAction.mutateAsync({ stepId, protocolId, action });
      toast.success(result.message || `Action ${action} executed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`);
    }
  };

  const openAssignDialog = (step: StepRun) => {
    setAssignStep(step);
    setSelectedAgentId(step.assigned_agent || step.engine_id || "");
  };

  const handleAssignAgent = async () => {
    if (!assignStep || !selectedAgentId) return;
    try {
      const result = await assignAgent.mutateAsync({
        stepId: assignStep.id,
        protocolId,
        agentId: selectedAgentId,
      });
      toast.success(result.message || "Agent assignment updated");
      setAssignStep(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign agent");
    }
  };

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
      cell: ({ row }) => (
        <span className="text-muted-foreground capitalize">{row.original.step_type}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusPill status={row.original.status} size="sm" />,
    },
    {
      accessorKey: "engine_id",
      header: "Engine",
      cell: ({ row }) => (
        <span className="font-mono text-sm">
          {row.original.assigned_agent || row.original.engine_id || "-"}
        </span>
      ),
    },
    {
      accessorKey: "retries",
      header: "Retries",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.retries}</span>,
    },
    {
      id: "policy",
      header: "Policy",
      cell: ({ row }) => {
        const policy = row.original.policy;
        if (!policy || !Array.isArray(policy.findings) || policy.findings.length === 0) {
          return <span className="text-muted-foreground">-</span>;
        }
        const findings = policy.findings as Array<{ severity: string }>;
        const errors = findings.filter((f) => f.severity === "error").length;
        const warnings = findings.filter((f) => f.severity === "warning").length;
        return (
          <div className="flex items-center gap-1">
            {errors > 0 && (
              <span className="inline-flex items-center gap-0.5 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5" /> {errors}
              </span>
            )}
            {warnings > 0 && (
              <span className="inline-flex items-center gap-0.5 text-xs text-yellow-500">
                <AlertTriangle className="h-3.5 w-3.5" /> {warnings}
              </span>
            )}
          </div>
        );
      },
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const step = row.original;
        const canRun = step.status === "pending";
        const canRunQA = ["completed", "failed", "blocked", "needs_qa"].includes(step.status);

        return (
          <div className="flex gap-1">
            {canRun && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction(step.id, "execute");
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
                  e.stopPropagation();
                  handleAction(step.id, "qa");
                }}
                disabled={stepAction.isPending}
              >
                <ClipboardCheck className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                openAssignDialog(step);
              }}
              disabled={!agents || agents.length === 0}
            >
              <Bot className="h-4 w-4" />
            </Button>
            <Link href={`/steps/${step.id}`}>
              <Button variant="ghost" size="sm">
                <ExternalLink className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        );
      },
    },
  ];

  if (isLoading) return <LoadingState message="Loading steps..." />;

  if (!steps || steps.length === 0) {
    return (
      <EmptyState
        icon={ListChecks}
        title="No steps yet"
        description="This protocol has no steps defined yet."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Steps</h3>
          <p className="text-muted-foreground text-sm">
            {steps.filter((s) => s.status === "completed").length} / {steps.length} completed
          </p>
        </div>
      </div>
      <DataTable
        columns={columns}
        data={steps}
        enableSearch
        enableExport
        enableColumnFilters
        exportFilename={`protocol-${protocolId}-steps.csv`}
      />
      <Dialog open={!!assignStep} onOpenChange={(open) => (!open ? setAssignStep(null) : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign Agent</DialogTitle>
            <DialogDescription>Select an agent to execute this step.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="assign-agent">Agent</Label>
              <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                <SelectTrigger id="assign-agent">
                  <SelectValue placeholder="Select agent" />
                </SelectTrigger>
                <SelectContent>
                  {(agents || []).map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAssignStep(null)}>
                Cancel
              </Button>
              <Button
                onClick={handleAssignAgent}
                disabled={!selectedAgentId || assignAgent.isPending}
              >
                Assign Agent
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
