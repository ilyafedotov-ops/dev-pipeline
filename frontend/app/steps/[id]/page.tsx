"use client";
import { use, useState } from "react";
import Link from "next/link";

import type { ColumnDef } from "@tanstack/react-table";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  ExternalLink,
  FileBox,
  FileText,
  Image,
  MessageSquare,
  Play,
  PlayCircle,
  RotateCcw,
  Send,
  ShieldCheck,
  XCircle as XCircleIcon,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusPill } from "@/components/ui/status-pill";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  useEscalateStep,
  useProtocol,
  useProtocolSteps,
  useStepAction,
  useStepArtifacts,
  useStepFeedbackEvents,
  useStepPolicyFindings,
  useStepQuality,
  useStepRun,
  useStepRuns,
  useSubmitStepFeedback,
  useTriggerRetry,
} from "@/lib/api";
import type { CodexRun, PolicyFinding, StepArtifact, StepQuality,StepRun } from "@/lib/api/types";
import type { FeedbackEvent } from "@/lib/api/hooks/use-feedback";
import { formatRelativeTime, truncateHash } from "@/lib/format";

export default function StepDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const stepId = Number.parseInt(id, 10);

  // Primary data source: fetch the step directly from the API
  const { data: stepData, isLoading: stepLoading } = useStepRun(stepId);

  // Secondary: get step runs (Codex runs) for this step
  const { data: runs, isLoading: runsLoading } = useStepRuns(stepId);

  // Get protocol info for context (back links, protocol name)
  const protocolRunId = stepData?.protocol_run_id;
  const { data: protocol } = useProtocol(protocolRunId ?? undefined);
  const { data: steps } = useProtocolSteps(protocolRunId ?? undefined);
  const { data: findings } = useStepPolicyFindings(stepId);
  const { data: artifacts } = useStepArtifacts(stepId);
  const { data: quality } = useStepQuality(stepId);
  const stepAction = useStepAction();
  const { data: stepFeedback, isLoading: stepFeedbackLoading } = useStepFeedbackEvents(stepId);
  const submitStepFeedback = useSubmitStepFeedback();
  const triggerRetry = useTriggerRetry();
  const escalateStep = useEscalateStep();

  const [stepFeedbackMessage, setStepFeedbackMessage] = useState("");

  // Use the direct step data as primary, fall back to protocol steps
  const step = steps?.find((s) => s.id === stepId);
  const resolvedData = stepData || step;

  if (stepLoading && !resolvedData) return <LoadingState message="Loading step..." />;

  // If we can't find the step, show basic view with runs
  const displayStep =
    resolvedData ||
    ({
      id: stepId,
      step_name: `Step ${stepId}`,
      step_type: "unknown",
      status: "pending",
      step_index: 0,
      retries: 0,
      protocol_run_id: protocolRunId || 0,
    } as StepRun);

  const handleAction = async (action: "execute" | "qa") => {
    if (!protocolRunId) return;
    try {
      const result = await stepAction.mutateAsync({
        stepId,
        protocolId: protocolRunId,
        action,
      });
      toast.success(result.message || `Action ${action} executed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`);
    }
  };

  const canRun = displayStep.status === "pending";
  const canRunQA = ["completed", "failed", "blocked", "needs_qa"].includes(displayStep.status);

  return (
    <div className="container py-8">
      <div className="mb-6">
        {protocol && (
          <>
            {protocol.project_id && (
              <Link
                href={`/projects/${protocol.project_id}`}
                className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Project
              </Link>
            )}
            <Link
              href={`/protocols/${protocol.id}`}
              className="text-muted-foreground hover:text-foreground mb-4 ml-4 inline-flex items-center gap-1 text-sm"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to {protocol.protocol_name}
            </Link>
          </>
        )}

        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold">
              {displayStep.step_name}
              <StatusPill status={displayStep.status} />
            </h1>
            <p className="text-muted-foreground mt-1 flex items-center gap-2">
              <span>Index: {displayStep.step_index}</span>
              <span className="text-muted-foreground">•</span>
              <span className="capitalize">Type: {displayStep.step_type}</span>
              {(displayStep.assigned_agent || displayStep.engine_id) && (
                <>
                  <span className="text-muted-foreground">•</span>
                  <span>Engine: {displayStep.assigned_agent || displayStep.engine_id}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex gap-2">
            {canRun && (
              <Button onClick={() => handleAction("execute")} disabled={stepAction.isPending}>
                <Play className="mr-2 h-4 w-4" />
                Execute
              </Button>
            )}
            {canRunQA && (
              <Button
                variant="secondary"
                onClick={() => handleAction("qa")}
                disabled={stepAction.isPending}
              >
                <ClipboardCheck className="mr-2 h-4 w-4" />
                Re-run QA
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mb-8 grid gap-4 md:grid-cols-4">
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
            <p className="font-medium">
              {displayStep.assigned_agent || displayStep.engine_id || "-"}
            </p>
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
          <TabsTrigger value="artifacts">
            Artifacts
            {artifacts && artifacts.length > 0 && (
              <span className="ml-1 rounded-full bg-blue-500/10 px-2 text-xs text-blue-500">
                {artifacts.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="policy">
            Policy Findings
            {findings && findings.length > 0 && (
              <span className="ml-1 rounded-full bg-yellow-500/10 px-2 text-xs text-yellow-500">
                {findings.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="feedback">
            Feedback
            {stepFeedback && stepFeedback.length > 0 && (
              <span className="ml-1 rounded-full bg-purple-500/10 px-2 text-xs text-purple-500">
                {stepFeedback.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
          <StepRunsTab runs={runs} isLoading={runsLoading} stepId={stepId} />
        </TabsContent>
        <TabsContent value="artifacts">
          <StepArtifactsTab artifacts={artifacts} stepId={stepId} />
        </TabsContent>
        <TabsContent value="quality">
          <StepQualityTab quality={quality} />
        </TabsContent>
        <TabsContent value="policy">
          <StepPolicyTab findings={findings} />
        </TabsContent>
        <TabsContent value="feedback" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Step Feedback
              </CardTitle>
              <CardDescription>
                {stepFeedback?.length || 0} feedback event(s) for this step
              </CardDescription>
            </CardHeader>
            <CardContent>
              {stepFeedbackLoading ? (
                <LoadingState message="Loading feedback..." />
              ) : !stepFeedback || stepFeedback.length === 0 ? (
                <EmptyState
                  icon={MessageSquare}
                  title="No feedback yet"
                  description="Submit feedback or trigger a retry for this step."
                />
              ) : (
                <div className="space-y-3">
                  {stepFeedback.map((fb: FeedbackEvent) => (
                    <div key={fb.id} className="flex items-start gap-3 rounded-lg border p-3">
                      <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px]">
                            {fb.event_type || "info"}
                          </Badge>
                          <span className="text-muted-foreground text-xs">
                            {formatRelativeTime(fb.created_at)}
                          </span>
                        </div>
                        {fb.action_taken && <p className="mt-1 text-sm">{fb.action_taken}</p>}
                        {fb.error_type && (
                          <p className="text-destructive text-xs">{fb.error_type}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Submit Feedback</CardTitle>
              <CardDescription>Provide feedback, retry, or escalate this step.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                id="step-feedback-message"
                value={stepFeedbackMessage}
                onChange={(e) => setStepFeedbackMessage(e.target.value)}
                placeholder="Enter feedback for this step..."
                rows={2}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    submitStepFeedback.mutate({
                      stepRunId: stepId,
                      action: "clarify",
                      message: stepFeedbackMessage,
                    });
                    setStepFeedbackMessage("");
                  }}
                  disabled={submitStepFeedback.isPending || !stepFeedbackMessage.trim()}
                >
                  <Send className="mr-2 h-3 w-3" />
                  {submitStepFeedback.isPending ? "Submitting..." : "Submit Feedback"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => triggerRetry.mutate({ stepRunId: stepId })}
                  disabled={triggerRetry.isPending}
                >
                  <RotateCcw className="mr-2 h-3 w-3" />
                  {triggerRetry.isPending ? "Retrying..." : "Trigger Retry"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => escalateStep.mutate({ stepRunId: stepId, reason: stepFeedbackMessage || "Manual escalation" })}
                  disabled={escalateStep.isPending}
                >
                  <AlertTriangle className="mr-2 h-3 w-3" />
                  {escalateStep.isPending ? "Escalating..." : "Escalate"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StepRunsTab({
  runs,
  isLoading,
  stepId,
}: {
  runs: CodexRun[] | undefined;
  isLoading: boolean;
  stepId: number;
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
      cell: ({ row }) => (
        <span className="text-muted-foreground">{formatRelativeTime(row.original.created_at)}</span>
      ),
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
  ];

  if (isLoading) return <LoadingState message="Loading runs..." />;

  if (!runs || runs.length === 0) {
    return (
      <EmptyState
        icon={PlayCircle}
        title="No runs yet"
        description="Execution runs will appear here."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Step Runs</h3>
        <p className="text-muted-foreground text-sm">{runs.length} run(s)</p>
      </div>
      <DataTable
        columns={columns}
        data={runs}
        enableSearch
        enableExport
        enableColumnFilters
        exportFilename={`step-${stepId}-runs.csv`}
      />
    </div>
  );
}

function artifactIcon(kind: string) {
  if (kind === "code" || kind === "diff") return Code2;
  if (kind === "image" || kind === "screenshot") return Image;
  return FileText;
}

function formatBytes(bytes: number | null) {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StepArtifactsTab({
  artifacts,
  stepId: _stepId,
}: {
  artifacts: StepArtifact[] | undefined;
  stepId: number;
}) {
  if (!artifacts || artifacts.length === 0) {
    return (
      <EmptyState
        icon={FileBox}
        title="No artifacts"
        description="Step artifacts will appear here after execution."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Step Artifacts</h3>
        <p className="text-muted-foreground text-sm">{artifacts.length} artifact(s)</p>
      </div>
      <div className="space-y-2">
        {artifacts.map((artifact) => {
          const Icon = artifactIcon(artifact.kind);
          return (
            <div key={artifact.id} className="flex items-center gap-3 rounded-lg border p-3">
              <Icon className="text-muted-foreground h-5 w-5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{artifact.name}</div>
                <div className="text-muted-foreground mt-1 flex items-center gap-3 text-xs">
                  <span>{artifact.kind}</span>
                  <span>{formatBytes(artifact.bytes)}</span>
                  <span className="truncate">{artifact.path}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function qualityStatusMeta(status: string) {
  if (status === "passed")
    {return { label: "Passed", icon: CheckCircle2, className: "text-green-600" };}
  if (status === "warning")
    {return { label: "Warning", icon: AlertTriangle, className: "text-amber-600" };}
  if (status === "failed") return { label: "Failed", icon: XCircleIcon, className: "text-red-600" };
  return { label: status || "Unknown", icon: ShieldCheck, className: "text-muted-foreground" };
}

function StepQualityTab({ quality }: { quality: StepQuality | undefined }) {
  if (!quality) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="No quality data"
        description="Run QA to populate quality results."
      />
    );
  }

  const overall = qualityStatusMeta(quality.overall_status);
  const OverallIcon = overall.icon;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <OverallIcon className={`h-5 w-5 ${overall.className}`} />
          Step Quality
        </CardTitle>
        <CardDescription>QA score and gate results</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4 text-sm">
          <span>
            Score: <strong>{Math.round(quality.score * 100)}%</strong>
          </span>
          <span>
            Blocking: <strong>{quality.blocking_issues}</strong>
          </span>
          <span>
            Warnings: <strong>{quality.warnings}</strong>
          </span>
        </div>
        {quality.gates.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Gates</h4>
            <div className="grid gap-2 md:grid-cols-2">
              {quality.gates.map((gate) => {
                const meta = qualityStatusMeta(gate.status);
                const GateIcon = meta.icon;
                return (
                  <div
                    key={`${gate.article}:${gate.name}`}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div>
                      <div className="text-sm font-medium">{gate.name}</div>
                      <div className="text-muted-foreground text-xs">{gate.article}</div>
                    </div>
                    <GateIcon className={`h-4 w-4 ${meta.className}`} />
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StepPolicyTab({ findings }: { findings: PolicyFinding[] | undefined }) {
  if (!findings || findings.length === 0) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="No findings"
        description="No policy findings for this step."
      />
    );
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
                className={`mt-0.5 h-5 w-5 ${finding.severity === "error" ? "text-destructive" : "text-yellow-500"}`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-muted-foreground font-mono text-sm">{finding.code}</p>
                <p className="mt-1">{finding.message}</p>
                {finding.suggested_fix && (
                  <p className="text-muted-foreground mt-1 text-sm">
                    Suggested fix: {finding.suggested_fix}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
