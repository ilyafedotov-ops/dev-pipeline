"use client";
import { use , useState } from "react";
import Link from "next/link";

import {
  ArrowLeft,
  ChevronDown,
  GitBranch,
  GitPullRequest,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  SkipForward,
  Workflow,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/ui/loading-state";
import { PolicyFindingsBanner } from "@/components/ui/policy-findings-banner";
import { StatusPill } from "@/components/ui/status-pill";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCreateProtocolFlow,
  useFeedbackAnswerClarification,
  useFeedbackEvents,
  useProject,
  useProtocol,
  useProtocolAction,
  useProtocolFlow,
  useProtocolPolicyFindings,
  useProtocolSprint,
  useSyncProtocolToSprint,
} from "@/lib/api";
import { formatRelativeTime, truncateHash } from "@/lib/format";
import { getSpecificationReviewPath } from "@/lib/project-routes";
import {
  describeProtocolTemplateConfig,
  formatProtocolTemplateSource,
} from "@/lib/protocol-template-display";
import { useWebSocketEvent } from "@/lib/websocket/hooks";

import { ArtifactsTab } from "./components/artifacts-tab";
import { ClarificationsTab } from "./components/clarifications-tab";
import { EventsTab } from "./components/events-tab";
import { FeedbackTab } from "./components/feedback-tab";
import { LogsTab } from "./components/logs-tab";
import { PolicyTab } from "./components/policy-tab";
import { QualityTab } from "./components/quality-tab";
import { RunsTab } from "./components/runs-tab";
import { SpecTab } from "./components/spec-tab";
import { StepsTab } from "./components/steps-tab";

const secondaryTabs = [
  { value: "events", label: "Events" },
  { value: "logs", label: "Logs" },
  { value: "spec", label: "Spec" },
  { value: "policy", label: "Policy" },
  { value: "clarifications", label: "Clarifications" },
  { value: "feedback", label: "Feedback" },
];

export default function ProtocolDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const protocolId = Number.parseInt(id, 10);
  const { data: protocol, isLoading: protocolLoading } = useProtocol(protocolId);
  const { data: project } = useProject(protocol?.project_id);
  const protocolAction = useProtocolAction();
  const { data: flowInfo } = useProtocolFlow(protocolId);
  const createFlow = useCreateProtocolFlow();
  const linkedSprintProtocolId = protocol?.linked_sprint_id ? protocolId : undefined;
  const { data: linkedSprint } = useProtocolSprint(linkedSprintProtocolId);
  const syncToSprint = useSyncProtocolToSprint();
  const [activeTab, setActiveTab] = useState("steps");

  // Feedback events for the protocol (real-time feedback log)
  const { data: feedbackEventData } = useFeedbackEvents(protocolId);
  const answerClarification = useFeedbackAnswerClarification();
  const { data: policyFindings } = useProtocolPolicyFindings(protocolId);

  // WebSocket real-time updates: listen for protocol & step changes
  const protocolChannel = `protocol:${protocolId}`;
  useWebSocketEvent(protocolChannel, ["step_started", "step_completed", "step_failed", "protocol_update"], (qc) => {
    qc.invalidateQueries({ queryKey: ["protocols", "detail", protocolId] });
    qc.invalidateQueries({ queryKey: ["protocols", "steps", protocolId] });
    qc.invalidateQueries({ queryKey: ["protocols", "runs", protocolId] });
    qc.invalidateQueries({ queryKey: ["protocols", "events", protocolId] });
    qc.invalidateQueries({ queryKey: ["protocols", "qualitySummary", protocolId] });
  });

  if (protocolLoading) return <LoadingState message="Loading protocol..." />;
  if (!protocol) return <LoadingState message="Protocol not found" />;

  const sprint = protocol.linked_sprint_id ? linkedSprint : null;

  const handleAction = async (
    action: Parameters<typeof protocolAction.mutateAsync>[0]["action"]
  ) => {
    try {
      const result = await protocolAction.mutateAsync({ protocolId, action });
      const message =
        typeof result === "object" &&
        result !== null &&
        "message" in result &&
        typeof result.message === "string"
          ? result.message
          : `Action ${action} executed`;
      toast.success(message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`);
    }
  };

  const canStart = protocol.status === "pending" || protocol.status === "planned";
  const canPause = protocol.status === "running";
  const canResume = protocol.status === "paused";
  const canCancel = ["running", "paused", "blocked", "planning"].includes(protocol.status);
  const canRunNext = protocol.status === "running" || protocol.status === "paused";
  const canRetry = protocol.status === "failed" || protocol.status === "blocked";
  const canOpenPR = protocol.status === "completed" || protocol.status === "running";
  const reviewPath =
    typeof protocol.speckit_metadata?.spec_run_id === "number"
      ? getSpecificationReviewPath(protocol.speckit_metadata.spec_run_id)
      : null;
  const templateSourceLabel = formatProtocolTemplateSource(protocol.template_source);
  const templateConfig = describeProtocolTemplateConfig(protocol.template_config);

  return (
    <div className="container py-8">
      <div className="mb-6">
        <Link
          href={`/projects/${protocol.project_id}`}
          className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {project?.name || "Project"}
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold">
              {protocol.protocol_name}
              <StatusPill status={protocol.status} />
            </h1>
            <p className="text-muted-foreground mt-1 flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              {protocol.base_branch}
              {protocol.spec_hash && (
                <>
                  <span className="text-muted-foreground">•</span>
                  <span className="font-mono text-xs">
                    Spec: {truncateHash(protocol.spec_hash)}
                  </span>
                </>
              )}
              {protocol.policy_pack_key && (
                <>
                  <span className="text-muted-foreground">•</span>
                  <span className="text-xs">Policy: {protocol.policy_pack_key}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            {reviewPath && (
              <Link href={reviewPath}>
                <Button variant="outline">
                  Review Implementation
                </Button>
              </Link>
            )}
            {canStart && (
              <Button onClick={() => handleAction("start")} disabled={protocolAction.isPending}>
                <Play className="mr-2 h-4 w-4" />
                Start
              </Button>
            )}
            {canPause && (
              <Button
                variant="secondary"
                onClick={() => handleAction("pause")}
                disabled={protocolAction.isPending}
              >
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            {canResume && (
              <Button onClick={() => handleAction("resume")} disabled={protocolAction.isPending}>
                <Play className="mr-2 h-4 w-4" />
                Resume
              </Button>
            )}
            {canRunNext && (
              <Button
                variant="secondary"
                onClick={() => handleAction("run_next_step")}
                disabled={protocolAction.isPending}
              >
                <SkipForward className="mr-2 h-4 w-4" />
                Run Next
              </Button>
            )}
            {canRetry && (
              <Button
                variant="secondary"
                onClick={() => handleAction("retry_latest")}
                disabled={protocolAction.isPending}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            )}
            {canOpenPR && (
              <Button
                variant="outline"
                onClick={() => handleAction("open_pr")}
                disabled={protocolAction.isPending}
              >
                <GitPullRequest className="mr-2 h-4 w-4" />
                Open PR
              </Button>
            )}
            {canCancel && (
              <Button
                variant="destructive"
                onClick={() => handleAction("cancel")}
                disabled={protocolAction.isPending}
              >
                <XCircle className="mr-2 h-4 w-4" />
                Cancel
              </Button>
            )}
            {!flowInfo?.flow_path && (
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await createFlow.mutateAsync(protocolId);
                    toast.success("Windmill flow created");
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Failed to create flow");
                  }
                }}
                disabled={createFlow.isPending}
              >
                <Workflow className="mr-2 h-4 w-4" />
                Create Flow
              </Button>
            )}
            {sprint && (
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await syncToSprint.mutateAsync({ protocolId, sprintId: sprint.id });
                    toast.success("Synced to sprint");
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Failed to sync to sprint");
                  }
                }}
                disabled={syncToSprint.isPending}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Sync Sprint
              </Button>
            )}
          </div>
        </div>

        {protocol.description && (
          <p className="text-muted-foreground mt-4">{protocol.description}</p>
        )}
        {(flowInfo?.flow_path || sprint) && (
          <div className="text-muted-foreground mt-3 flex items-center gap-4 text-sm">
            {flowInfo?.flow_path && (
              <span className="flex items-center gap-1">
                <Workflow className="h-3.5 w-3.5" />
                Flow: <code className="bg-muted rounded px-1 text-xs">{flowInfo.flow_path}</code>
              </span>
            )}
            {sprint && (
              <span className="flex items-center gap-1">
                Sprint: <strong className="text-foreground">{sprint.name}</strong>
              </span>
            )}
          </div>
        )}
      </div>

      <div className="mb-8 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
          </CardHeader>
          <CardContent>
            <StatusPill status={protocol.status} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Spec Status</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium capitalize">{protocol.spec_validation_status || "N/A"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Policy Pack</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{protocol.policy_pack_key || "None"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Template Source</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="truncate font-medium" title={templateSourceLabel}>
              {templateSourceLabel}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Template Config</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{templateConfig.summary}</p>
            {templateConfig.detail && (
              <p className="text-muted-foreground mt-1 truncate text-xs" title={templateConfig.detail}>
                {templateConfig.detail}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Created</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{formatRelativeTime(protocol.created_at)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Feedback Events</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{feedbackEventData?.total ?? feedbackEventData?.events?.length ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      {policyFindings && policyFindings.length > 0 && (
        <PolicyFindingsBanner findings={policyFindings} scope="protocol" />
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <div className="flex items-center gap-1">
          <TabsList>
            <TabsTrigger value="steps">Steps</TabsTrigger>
            <TabsTrigger value="runs">Runs</TabsTrigger>
            <TabsTrigger value="quality">Quality</TabsTrigger>
            <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
          </TabsList>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="text-muted-foreground h-9 gap-1">
                {secondaryTabs.find((t) => t.value === activeTab)?.label || "More"}
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {secondaryTabs.map((tab) => (
                <DropdownMenuItem key={tab.value} onClick={() => setActiveTab(tab.value)}>
                  {tab.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <TabsContent value="steps">
          <StepsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="runs">
          <RunsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="quality">
          <QualityTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="artifacts">
          <ArtifactsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="events">
          <EventsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="spec">
          <SpecTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="policy">
          <PolicyTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="clarifications">
          <ClarificationsTab protocolId={protocolId} />
        </TabsContent>
        <TabsContent value="feedback">
          <FeedbackTab protocolId={protocolId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
