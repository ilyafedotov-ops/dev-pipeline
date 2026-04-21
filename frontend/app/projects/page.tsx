"use client";

import { type KeyboardEvent,useState } from "react";
import { useRouter } from "next/navigation";

import {
  Activity,
  AlertCircle,
  Archive,
  ArchiveRestore,
  CheckCircle2,
  Cloud,
  Copy,
  ExternalLink,
  FileText,
  FolderGit2,
  FolderOpen,
  GitBranch,
  LayoutGrid,
  List,
  Loader2,
  MoreVertical,
  Play,
  Plus,
  Search,
  Settings,
  Trash2,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { Progress } from "@/components/ui/progress";
import { ProjectWizard } from "@/components/wizards/project-wizard";
import {
  useArchiveProject,
  useCreateProject,
  useDeleteProject,
  useOnboarding,
  useProjects,
  useUnarchiveProject,
} from "@/lib/api";
import type { Project } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ProjectsPage() {
  const { data: projects, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const archiveProject = useArchiveProject();
  const unarchiveProject = useUnarchiveProject();
  const deleteProject = useDeleteProject();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const router = useRouter();

  const filteredProjects =
    projects?.filter(
      (p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.git_url.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  if (isLoading) return <LoadingState message="Loading projects..." />;
  if (error) return <EmptyState title="Error loading projects" description={error.message} />;

  const stats = {
    total: projects?.length || 0,
    active:
      projects?.filter(
        (p) => p.policy_enforcement_mode === "warn" || p.policy_enforcement_mode === "block"
      ).length || 0,
    withPolicy: projects?.filter((p) => p.policy_pack_key).length || 0,
  };

  const handleOpenProject = (projectId: number) => {
    router.push(`/projects/${projectId}`);
  };

  const handleRunProtocol = (projectId: number) => {
    router.push(`/projects/${projectId}?tab=workflow`);
  };

  const handleViewSpecs = (projectId: number) => {
    router.push(`/projects/${projectId}?tab=spec`);
  };

  const handleSettings = (projectId: number) => {
    router.push(`/projects/${projectId}?tab=policy`);
  };

  const handleOpenGit = (project: Project) => {
    if (!project.git_url) {
      toast.error("No repository URL configured for this project.");
      return;
    }
    window.open(project.git_url, "_blank", "noopener,noreferrer");
  };

  const handleArchiveToggle = async (project: Project) => {
    try {
      if (project.status === "archived") {
        await unarchiveProject.mutateAsync(project.id);
        toast.success(`Unarchived ${project.name}`);
      } else {
        await archiveProject.mutateAsync(project.id);
        toast.success(`Archived ${project.name}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update project status");
    }
  };

  const handleDuplicate = async (project: Project) => {
    if (!project.git_url) {
      toast.error("Cannot duplicate a project without a repository URL.");
      return;
    }
    const suggestedName = `${project.name} Copy`;
    const name = window.prompt("Name for the duplicated project:", suggestedName);
    if (!name) return;

    try {
      const created = await createProject.mutateAsync({
        name,
        git_url: project.git_url,
        base_branch: project.base_branch,
      });
      toast.success(`Created ${created.name}`);
      router.push(`/projects/${created.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to duplicate project");
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteProject.mutateAsync(deleteTarget.id);
      toast.success(`Deleted ${deleteTarget.name}`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete project");
    }
  };

  return (
    <div className="container space-y-8 py-8">
      <div>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
            <p className="text-muted-foreground mt-1">
              Manage your registered repositories and development workflows
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center rounded-lg border p-1">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setViewMode("grid")}
                className="h-8 w-8 p-0"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setViewMode("list")}
                className="h-8 w-8 p-0"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
            <Button onClick={() => setIsCreateOpen(true)} size="lg">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Button>
          </div>
        </div>

        <div className="bg-muted/50 mb-6 rounded-lg border p-4">
          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-500/10">
                <FolderGit2 className="h-4 w-4 text-blue-500" />
              </div>
              <div>
                <div className="text-muted-foreground text-sm font-medium">Total Projects</div>
                <div className="text-2xl font-bold">{stats.total}</div>
              </div>
            </div>

            <div className="bg-border h-12 w-px" />

            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-purple-500/10">
                <Activity className="h-4 w-4 text-purple-500" />
              </div>
              <div>
                <div className="text-muted-foreground text-sm font-medium">Active</div>
                <div className="text-2xl font-bold">{stats.active}</div>
              </div>
            </div>

            <div className="bg-border h-12 w-px" />

            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-green-500/10">
                <TrendingUp className="h-4 w-4 text-green-500" />
              </div>
              <div>
                <div className="text-muted-foreground text-sm font-medium">With Policy</div>
                <div className="text-2xl font-bold">{stats.withPolicy}</div>
              </div>
            </div>

            <div className="flex-1" />

            <div className="text-right">
              <div className="text-muted-foreground mb-1 text-xs tracking-wider uppercase">
                Quick Actions
              </div>
              <Button variant="outline" size="sm" onClick={() => setIsCreateOpen(true)}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add Project
              </Button>
            </div>
          </div>
        </div>

        <div className="relative">
          <Search className="text-muted-foreground absolute top-3 left-3 h-4 w-4" />
          <Input
            placeholder="Search projects by name or repository..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-11 pl-9"
          />
        </div>
      </div>

      {!filteredProjects || filteredProjects.length === 0 ? (
        <EmptyState
          icon={FolderGit2}
          title={searchQuery ? "No projects found" : "No projects yet"}
          description={
            searchQuery
              ? "Try adjusting your search query."
              : "Create your first project to get started with DevGodzilla."
          }
          action={
            !searchQuery ? (
              <Button onClick={() => setIsCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Project
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div
          className={cn(
            viewMode === "grid" && "grid gap-6 md:grid-cols-2 lg:grid-cols-3",
            viewMode === "list" && "space-y-4"
          )}
        >
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              viewMode={viewMode}
              onOpen={handleOpenProject}
              onRunProtocol={handleRunProtocol}
              onViewSpecs={handleViewSpecs}
              onSettings={handleSettings}
              onDuplicate={handleDuplicate}
              onOpenGit={handleOpenGit}
              onArchiveToggle={handleArchiveToggle}
              onDeleteRequest={setDeleteTarget}
            />
          ))}
        </div>
      )}

      <ProjectWizard open={isCreateOpen} onOpenChange={setIsCreateOpen} />
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove {deleteTarget?.name} and all associated runs, specs, and
              events. Local repository files are not removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function OnboardingProgress({ projectId }: { projectId: number }) {
  const { data: onboarding, isLoading } = useOnboarding(projectId);

  if (isLoading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>Loading...</span>
      </div>
    );
  }

  if (!onboarding) return null;

  const completedStages = onboarding.stages?.filter((s) => s.status === "completed").length || 0;
  const totalStages = onboarding.stages?.length || 4;
  const progress = Math.round((completedStages / totalStages) * 100);

  const statusIcon = {
    pending: <AlertCircle className="text-muted-foreground h-3 w-3" />,
    running: <Loader2 className="h-3 w-3 animate-spin text-blue-500" />,
    completed: <CheckCircle2 className="h-3 w-3 text-green-500" />,
    failed: <XCircle className="h-3 w-3 text-red-500" />,
    blocked: <AlertCircle className="h-3 w-3 text-amber-500" />,
  }[onboarding.status] || <AlertCircle className="text-muted-foreground h-3 w-3" />;

  const statusLabel =
    {
      pending: "Pending",
      running: "Onboarding...",
      completed: "Ready",
      failed: "Failed",
      blocked: "Blocked",
    }[onboarding.status] || onboarding.status;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs">
        {statusIcon}
        <span
          className={cn(
            "capitalize",
            onboarding.status === "completed" && "text-green-600",
            onboarding.status === "failed" && "text-red-600",
            onboarding.status === "blocked" && "text-amber-600",
            onboarding.status === "running" && "text-blue-600"
          )}
        >
          {statusLabel}
        </span>
        {onboarding.blocking_clarifications > 0 && (
          <Badge variant="destructive" className="h-4 px-1 text-[10px]">
            {onboarding.blocking_clarifications} blocked
          </Badge>
        )}
      </div>
      {onboarding.status !== "completed" && onboarding.status !== "pending" && (
        <Progress value={progress} className="h-1" />
      )}
    </div>
  );
}

function CloneStatusIndicator({ localPath }: { localPath: string | null }) {
  if (localPath) {
    return (
      <div
        className="flex items-center gap-1 text-xs text-green-600"
        title={`Cloned: ${localPath}`}
      >
        <FolderOpen className="h-3 w-3" />
        <span>Local</span>
      </div>
    );
  }
  return (
    <div
      className="text-muted-foreground flex items-center gap-1 text-xs"
      title="Not cloned locally"
    >
      <Cloud className="h-3 w-3" />
      <span>Remote</span>
    </div>
  );
}

type ProjectCardProps = {
  project: Project;
  viewMode: "grid" | "list";
  onOpen: (projectId: number) => void;
  onRunProtocol: (projectId: number) => void;
  onViewSpecs: (projectId: number) => void;
  onSettings: (projectId: number) => void;
  onDuplicate: (project: Project) => void;
  onOpenGit: (project: Project) => void;
  onArchiveToggle: (project: Project) => void;
  onDeleteRequest: (project: Project | null) => void;
};

function ProjectCard({
  project,
  viewMode,
  onOpen,
  onRunProtocol,
  onViewSpecs,
  onSettings,
  onDuplicate,
  onOpenGit,
  onArchiveToggle,
  onDeleteRequest,
}: ProjectCardProps) {
  const [showActions, setShowActions] = useState(false);
  const isArchived = project.status === "archived";

  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen(project.id);
    }
  };

  return (
    <div
      className={cn("group relative", viewMode === "list" && "flex items-center gap-4")}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <Card
        role="button"
        tabIndex={0}
        onKeyDown={handleCardKeyDown}
        onClick={() => onOpen(project.id)}
        className={cn(
          "hover:border-primary/50 h-full cursor-pointer transition-all hover:shadow-lg",
          viewMode === "list" && "flex flex-1 items-center"
        )}
      >
        <CardHeader
          className={cn("pb-4", viewMode === "list" && "flex-row items-center space-y-0 py-4")}
        >
          <div className="flex flex-1 items-start justify-between">
            <div className="flex min-w-0 flex-1 items-center gap-4">
              <div className="relative">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-neutral-600 to-neutral-800 text-lg font-bold text-white">
                  {project.name.charAt(0).toUpperCase()}
                </div>
                {project.policy_enforcement_mode && (
                  <div className="border-background absolute -right-1 -bottom-1 flex h-5 w-5 items-center justify-center rounded-full border-2 bg-neutral-700">
                    <Activity className="h-3 w-3 text-white" />
                  </div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <CardTitle className="group-hover:text-primary truncate text-lg transition-colors">
                  {project.name}
                </CardTitle>
                <CardDescription className="mt-1 flex items-center gap-2 text-xs">
                  <GitBranch className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">{project.base_branch}</span>
                </CardDescription>
              </div>
            </div>

            {viewMode === "grid" && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(event) => event.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      "h-8 w-8 p-0 opacity-0 transition-opacity group-hover:opacity-100",
                      showActions && "opacity-100"
                    )}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onRunProtocol(project.id);
                    }}
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Run Protocol
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onViewSpecs(project.id);
                    }}
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    View Specs
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onSettings(project.id);
                    }}
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onDuplicate(project);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onOpenGit(project);
                    }}
                    disabled={!project.git_url}
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open in GitHub
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      onArchiveToggle(project);
                    }}
                  >
                    {isArchived ? (
                      <ArchiveRestore className="mr-2 h-4 w-4" />
                    ) : (
                      <Archive className="mr-2 h-4 w-4" />
                    )}
                    {isArchived ? "Unarchive" : "Archive"}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDeleteRequest(project);
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </CardHeader>

        {viewMode === "grid" && (
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <OnboardingProgress projectId={project.id} />
              <CloneStatusIndicator localPath={project.local_path} />
            </div>

            <div className="flex items-center gap-2 text-xs">
              <code className="bg-muted flex-1 truncate rounded px-2 py-1.5 font-mono text-[10px]">
                {project.git_url.replace("https://", "").replace("http://", "")}
              </code>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpenGit(project);
                }}
                disabled={!project.git_url}
              >
                <ExternalLink className="h-3 w-3" />
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {project.policy_pack_key && (
                <Badge variant="secondary" className="text-xs">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {project.policy_pack_key}
                </Badge>
              )}
              {project.policy_enforcement_mode && (
                <Badge
                  variant={
                    project.policy_enforcement_mode === "block"
                      ? "default"
                      : project.policy_enforcement_mode === "warn"
                        ? "secondary"
                        : "outline"
                  }
                  className="text-xs capitalize"
                >
                  {project.policy_enforcement_mode}
                </Badge>
              )}
              {project.project_classification && (
                <Badge variant="outline" className="text-xs">
                  {project.project_classification}
                </Badge>
              )}
            </div>

            <div className="flex items-center justify-between border-t pt-3">
              <span className="text-muted-foreground text-xs">
                Updated {formatRelativeTime(project.updated_at)}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpen(project.id);
                }}
              >
                View Details →
              </Button>
            </div>
          </CardContent>
        )}

        {viewMode === "list" && (
          <CardContent className="flex items-center gap-4 py-4">
            <div className="flex flex-1 items-center gap-2">
              {project.policy_pack_key && (
                <Badge variant="secondary" className="text-xs">
                  {project.policy_pack_key}
                </Badge>
              )}
              {project.policy_enforcement_mode && (
                <Badge variant="outline" className="text-xs capitalize">
                  {project.policy_enforcement_mode}
                </Badge>
              )}
            </div>
            <span className="text-muted-foreground text-xs whitespace-nowrap">
              {formatRelativeTime(project.updated_at)}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(event) => event.stopPropagation()}>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onRunProtocol(project.id);
                  }}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Run Protocol
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onViewSpecs(project.id);
                  }}
                >
                  <FileText className="mr-2 h-4 w-4" />
                  View Specs
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onSettings(project.id);
                  }}
                >
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onDuplicate(project);
                  }}
                >
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenGit(project);
                  }}
                  disabled={!project.git_url}
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Open in GitHub
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onArchiveToggle(project);
                  }}
                >
                  {isArchived ? (
                    <ArchiveRestore className="mr-2 h-4 w-4" />
                  ) : (
                    <Archive className="mr-2 h-4 w-4" />
                  )}
                  {isArchived ? "Unarchive" : "Archive"}
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-destructive"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteRequest(project);
                  }}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
