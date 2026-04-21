"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";

import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cloud,
  ExternalLink,
  FileCode2,
  FileSearch,
  FolderOpen,
  GitCommit,
  GitPullRequest,
  MessageCircle,
  PlayCircle,
  Plus,
  Shield,
  Workflow,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { SpecWorkflow } from "@/components/speckit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusPill } from "@/components/ui/status-pill";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateProtocol,
  useOnboarding,
  usePolicyFindings,
  useProject,
  useProjectCommits,
  useProjectProtocols,
  useProjectPulls,
  useSpecKitStatus,
} from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import {
  getProjectExecutionPath,
  getProjectSpecWorkflowPath,
  getProjectSpecWorkspaceStepPath,
  getSpecificationReviewPath,
} from "@/lib/project-routes";
import { parseTemplateConfigInput } from "@/lib/protocol-create";
import {
  describeProtocolTemplateConfig,
  formatProtocolTemplateSource,
} from "@/lib/protocol-template-display";
import { cn } from "@/lib/utils";

interface OverviewTabProps {
  projectId: number;
}

export function OverviewTab({ projectId }: OverviewTabProps) {
  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const { data: onboarding, isLoading: onboardingLoading } = useOnboarding(projectId);
  const { data: protocols } = useProjectProtocols(projectId);
  const { data: specKitStatus } = useSpecKitStatus(projectId);
  const { data: policyFindings } = usePolicyFindings(projectId);
  const { data: commits } = useProjectCommits(projectId);
  const { data: pulls } = useProjectPulls(projectId);
  const [isCreateProtocolOpen, setIsCreateProtocolOpen] = useState(false);

  const activeSpecMeta = useMemo(() => {
    const candidates = (specKitStatus?.specs ?? []).filter(
      (s) => s.status !== "cleaned" && (s.spec_path || s.path)
    );
    return candidates[0] ?? null;
  }, [specKitStatus]);

  const activeSpecReviewPath = useMemo(() => {
    if (!activeSpecMeta?.id) return null;
    const hasReviewSurface = Boolean(
      activeSpecMeta.has_tasks ||
        activeSpecMeta.checklist_path ||
        activeSpecMeta.analysis_path ||
        activeSpecMeta.implement_path
    );
    return hasReviewSurface ? getSpecificationReviewPath(activeSpecMeta.id) : null;
  }, [activeSpecMeta]);

  const workflowStatus = useMemo(() => {
    const hasSpec = Boolean(
      activeSpecMeta?.has_spec ?? activeSpecMeta?.spec_path ?? activeSpecMeta?.path
    );
    const hasPlan = Boolean(activeSpecMeta?.has_plan ?? activeSpecMeta?.plan_path);
    const hasTasks = Boolean(activeSpecMeta?.has_tasks ?? activeSpecMeta?.tasks_path);
    const hasChecklist = Boolean(activeSpecMeta?.checklist_path);
    const hasAnalysis = Boolean(activeSpecMeta?.analysis_path);
    const hasImplement = Boolean(activeSpecMeta?.implement_path);
    return {
      spec: hasSpec ? "completed" : "pending",
      clarify: "pending",
      plan: hasPlan ? "completed" : "pending",
      checklist: hasChecklist ? "completed" : "pending",
      tasks: hasTasks ? "completed" : "pending",
      analyze: hasAnalysis ? "completed" : "pending",
      implement: hasImplement ? "completed" : "pending",
      sprint: "pending",
    } as const;
  }, [activeSpecMeta]);

  const currentWorkflowStep = useMemo(() => {
    if (workflowStatus.spec !== "completed") return "spec" as const;
    if (workflowStatus.plan !== "completed") return "plan" as const;
    if (workflowStatus.tasks !== "completed") return "tasks" as const;
    if (workflowStatus.implement !== "completed") return "implement" as const;
    return "sprint" as const;
  }, [workflowStatus]);

  if (projectLoading || onboardingLoading) return <LoadingState message="Loading overview..." />;

  const runningCount = protocols?.filter((p) => p.status === "running").length ?? 0;
  const failedCount = protocols?.filter((p) => p.status === "failed").length ?? 0;
  const openPRCount = pulls?.filter((p) => p.status === "open").length ?? 0;
  const errorFindingCount = policyFindings?.filter((f) => f.severity === "error").length ?? 0;
  const warningFindingCount =
    policyFindings?.filter((f) => f.severity === "warning").length ?? 0;
  const policyFindingCount = policyFindings?.length ?? 0;
  const blockingClarifications = onboarding?.blocking_clarifications ?? 0;

  const nextAction = resolveNextAction({
    projectId,
    step: currentWorkflowStep,
    activeSpecReviewPath,
  });
  const NextActionIcon = nextAction.icon;

  return (
    <div className="space-y-6">
      {/* KPI card row — replaces top status strip + legacy 4 stat cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          href={onboarding ? `/projects/${projectId}?tab=onboarding` : `/projects/${projectId}?tab=settings`}
          icon={Activity}
          iconClassName="text-blue-500"
          label="Onboarding"
        >
          {onboarding ? (
            <StatusPill status={onboarding.status} size="sm" />
          ) : (
            <span className="text-muted-foreground text-sm">Not started</span>
          )}
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=protocols`}
          icon={Workflow}
          iconClassName="text-purple-500"
          label="Protocols"
        >
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold">{protocols?.length ?? 0}</span>
            <span className="text-muted-foreground text-xs">
              {runningCount} running{failedCount > 0 ? ` · ${failedCount} failed` : ""}
            </span>
          </div>
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=policy`}
          icon={Shield}
          iconClassName="text-green-500"
          label="Policy"
          sublabel={project?.policy_pack_key || "no pack"}
        >
          {policyFindingCount === 0 ? (
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="text-sm">No issues</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {errorFindingCount > 0 ? (
                <XCircle className="h-4 w-4 text-red-500" />
              ) : warningFindingCount > 0 ? (
                <AlertTriangle className="h-4 w-4 text-amber-500" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              )}
              <span className="text-sm font-medium">{policyFindingCount} findings</span>
              {errorFindingCount > 0 && (
                <Badge variant="destructive" className="h-5">
                  {errorFindingCount} err
                </Badge>
              )}
              {warningFindingCount > 0 && (
                <Badge variant="secondary" className="h-5">
                  {warningFindingCount} warn
                </Badge>
              )}
            </div>
          )}
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=clarifications`}
          icon={MessageCircle}
          iconClassName={blockingClarifications > 0 ? "text-amber-500" : "text-muted-foreground"}
          label="Blockers"
        >
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                "text-2xl font-bold",
                blockingClarifications > 0 && "text-amber-600"
              )}
            >
              {blockingClarifications}
            </span>
            <span className="text-muted-foreground text-xs">clarifications</span>
          </div>
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=branches`}
          icon={GitCommit}
          iconClassName="text-muted-foreground"
          label="Last Commit"
        >
          {commits && commits.length > 0 ? (
            <div className="space-y-0.5">
              <p className="truncate font-mono text-sm">{commits[0].sha.slice(0, 7)}</p>
              <p className="text-muted-foreground truncate text-xs">{commits[0].message}</p>
              <p className="text-muted-foreground text-xs">
                {formatRelativeTime(commits[0].date)}
              </p>
            </div>
          ) : (
            <p className="text-muted-foreground text-xs">No commits</p>
          )}
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=branches`}
          icon={GitPullRequest}
          iconClassName="text-muted-foreground"
          label="Open PRs"
        >
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold">{openPRCount}</span>
            <span className="text-muted-foreground text-xs">
              {pulls && pulls.length > 0
                ? `${pulls.length} total`
                : "No pull requests"}
            </span>
          </div>
        </KpiCard>

        <KpiCard
          href={`/projects/${projectId}?tab=protocols`}
          icon={Workflow}
          iconClassName="text-muted-foreground"
          label="Running"
        >
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold">{runningCount}</span>
            <span className="text-muted-foreground text-xs">
              {failedCount} failed
            </span>
          </div>
        </KpiCard>

        {project?.git_url ? (
          <KpiCard
            href={project.git_url}
            external
            icon={project.local_path ? FolderOpen : Cloud}
            iconClassName={project.local_path ? "text-green-500" : "text-muted-foreground"}
            label="Repo"
            sublabel={project.base_branch}
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">
                {project.local_path ? "Local working copy" : "Remote"}
              </span>
              <ExternalLink className="text-muted-foreground h-3.5 w-3.5" />
            </div>
          </KpiCard>
        ) : (
          <KpiCard
            href={`/projects/${projectId}?tab=settings`}
            icon={Cloud}
            iconClassName="text-muted-foreground"
            label="Repo"
          >
            <span className="text-muted-foreground text-sm">Not configured</span>
          </KpiCard>
        )}
      </div>

      {/* Next Action CTA — single prominent button driven by workflow state */}
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
          <div className="flex items-center gap-3">
            <NextActionIcon className="text-primary h-5 w-5" />
            <div>
              <p className="text-sm font-semibold">{nextAction.title}</p>
              <p className="text-muted-foreground text-xs">{nextAction.description}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsCreateProtocolOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Protocol
            </Button>
            <Button asChild>
              <Link href={nextAction.href}>
                {nextAction.cta}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <SpecWorkflow
        projectId={projectId}
        currentStep={currentWorkflowStep}
        stepStatus={workflowStatus}
        showActions
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>Recent Protocols</CardTitle>
            <CardDescription>Latest protocol activity</CardDescription>
          </div>
          {protocols && protocols.length > 0 && (
            <Link
              href={`/projects/${projectId}?tab=protocols`}
              className="text-primary text-sm hover:underline"
            >
              View all →
            </Link>
          )}
        </CardHeader>
        <CardContent>
          {protocols && protocols.length > 0 ? (
            <div className="space-y-2">
              {protocols.slice(0, 5).map((protocol) => (
                <Link
                  key={protocol.id}
                  href={`/protocols/${protocol.id}`}
                  className="hover:bg-accent flex items-center justify-between gap-4 rounded-lg p-2 transition-colors"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <FileCode2 className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{protocol.protocol_name}</p>
                      <p className="text-muted-foreground text-xs">
                        {formatRelativeTime(protocol.created_at)}
                        <span className="mx-1">·</span>
                        <span title={formatProtocolTemplateSource(protocol.template_source)}>
                          {formatProtocolTemplateSource(protocol.template_source)}
                        </span>
                      </p>
                      <p
                        className="text-muted-foreground truncate text-xs"
                        title={
                          describeProtocolTemplateConfig(protocol.template_config).detail ??
                          undefined
                        }
                      >
                        Config: {describeProtocolTemplateConfig(protocol.template_config).summary}
                      </p>
                    </div>
                  </div>
                  <StatusPill status={protocol.status} size="sm" />
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No protocols yet</p>
          )}
        </CardContent>
      </Card>

      {onboarding && onboarding.blocking_clarifications > 0 && (
        <Card className="border-yellow-500/50 bg-yellow-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-yellow-500" />
              Attention Required
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              This project has {onboarding.blocking_clarifications} blocking clarification
              {onboarding.blocking_clarifications > 1 ? "s" : ""} that need your response.
            </p>
            <Button variant="outline" className="mt-4 bg-transparent" asChild>
              <Link href={`/projects/${projectId}?tab=clarifications`}>View Clarifications</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <CreateProtocolDialog
        projectId={projectId}
        open={isCreateProtocolOpen}
        onClose={() => setIsCreateProtocolOpen(false)}
      />
    </div>
  );
}

// ─── Next-action CTA resolver ──────────────────────────────────────────────────

type NextActionCtx = {
  projectId: number;
  step: "spec" | "plan" | "tasks" | "implement" | "sprint";
  activeSpecReviewPath: string | null;
};

type NextAction = {
  title: string;
  description: string;
  cta: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
};

function resolveNextAction({ projectId, step, activeSpecReviewPath }: NextActionCtx): NextAction {
  switch (step) {
    case "spec":
      return {
        title: "Start a specification",
        description: "Draft the first SpecKit spec to kick off this project",
        cta: "Run Spec Workflow",
        href: getProjectSpecWorkflowPath(projectId),
        icon: Workflow,
      };
    case "plan":
      return {
        title: "Generate the implementation plan",
        description: "Your spec is ready — design the architecture next",
        cta: "Open Spec Workspace",
        href: getProjectSpecWorkspaceStepPath(projectId, "plan"),
        icon: FileCode2,
      };
    case "tasks":
      return {
        title: "Break the plan into tasks",
        description: "Plan is ready — generate the task list",
        cta: "Open Spec Workspace",
        href: getProjectSpecWorkspaceStepPath(projectId, "tasks"),
        icon: FileCode2,
      };
    case "implement":
      if (activeSpecReviewPath) {
        return {
          title: "Review the active implementation",
          description: "Implementation has started — review progress",
          cta: "Review Implementation",
          href: activeSpecReviewPath,
          icon: FileSearch,
        };
      }
      return {
        title: "Kick off implementation",
        description: "Tasks are ready — initialize the implementation run",
        cta: "Open Spec Workspace",
        href: getProjectSpecWorkspaceStepPath(projectId, "implement"),
        icon: PlayCircle,
      };
    case "sprint":
    default:
      return {
        title: "Track execution",
        description: "Implementation initialized — assign work to a sprint",
        cta: "Open Execution",
        href: getProjectExecutionPath(projectId),
        icon: PlayCircle,
      };
  }
}

// ─── KPI card ──────────────────────────────────────────────────────────────────

interface KpiCardProps {
  href: string;
  external?: boolean;
  icon: React.ComponentType<{ className?: string }>;
  iconClassName?: string;
  label: string;
  sublabel?: string;
  children: React.ReactNode;
}

function KpiCard({
  href,
  external,
  icon: Icon,
  iconClassName,
  label,
  sublabel,
  children,
}: KpiCardProps) {
  const body = (
    <Card className="hover:border-primary/40 hover:bg-accent/30 h-full cursor-pointer transition-colors">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-wider uppercase">
          <Icon className={cn("h-4 w-4", iconClassName)} />
          <span className="text-muted-foreground">{label}</span>
          {sublabel && (
            <code className="bg-muted ml-auto rounded px-1.5 py-0.5 font-mono text-[10px] normal-case tracking-normal">
              {sublabel}
            </code>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="block h-full">
        {body}
      </a>
    );
  }

  return (
    <Link href={href} className="block h-full">
      {body}
    </Link>
  );
}

// ─── Create-protocol dialog (unchanged) ────────────────────────────────────────

function CreateProtocolDialog({
  projectId,
  open,
  onClose,
}: {
  projectId: number;
  open: boolean;
  onClose: () => void;
}) {
  const createProtocol = useCreateProtocol();
  const [formData, setFormData] = useState({
    protocol_name: "",
    description: "",
    template_source: "",
    template_config: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const templateConfig = parseTemplateConfigInput(formData.template_config);
      await createProtocol.mutateAsync({
        projectId: projectId,
        data: {
          protocol_name: formData.protocol_name,
          description: formData.description || undefined,
          template_source: formData.template_source || undefined,
          template_config: templateConfig,
        },
      });
      toast.success("Protocol created successfully");
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create protocol");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create New Protocol</DialogTitle>
          <DialogDescription>Define a new protocol for this project.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="protocol_name">Protocol Name</Label>
              <Input
                id="protocol_name"
                placeholder="0001-feature-auth"
                value={formData.protocol_name}
                onChange={(e) =>
                  setFormData((p) => ({ ...p, protocol_name: e.target.value }))
                }
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                placeholder="Implement authentication system"
                value={formData.description}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template_source">Template Source (optional)</Label>
              <Input
                id="template_source"
                placeholder="./templates/feature.yaml"
                value={formData.template_source}
                onChange={(e) =>
                  setFormData((p) => ({ ...p, template_source: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template_config">Template Config (JSON object, optional)</Label>
              <Textarea
                id="template_config"
                className="min-h-48 font-mono text-sm"
                placeholder='{ "mode": "guided" }'
                value={formData.template_config}
                onChange={(e) =>
                  setFormData((p) => ({ ...p, template_config: e.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={createProtocol.isPending}>
              {createProtocol.isPending ? "Creating..." : "Create Protocol"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
