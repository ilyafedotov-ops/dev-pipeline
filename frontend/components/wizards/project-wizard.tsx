"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { CheckCircle2, GitBranch, Loader2,type LucideIcon, Shield } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { ApiError } from "@/lib/api/client";
import { usePolicyPacks } from "@/lib/api/hooks/use-policy-packs";
import { useCreateProject } from "@/lib/api/hooks/use-projects";
import type { PolicyEnforcementMode } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface ProjectWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type WizardStep = "git" | "policy" | "onboarding";

const steps: { id: WizardStep; label: string; icon: LucideIcon }[] = [
  { id: "git", label: "Git Repository", icon: GitBranch },
  { id: "policy", label: "Policy Pack", icon: Shield },
  { id: "onboarding", label: "Review & Start", icon: CheckCircle2 },
];

const classificationOrder = [
  "default",
  "beginner-guided",
  "startup-fast",
  "team-standard",
  "enterprise-compliance",
] as const;

const classificationRank = new Map<string, number>(
  classificationOrder.map((value, index) => [value, index])
);

function looksLikeGitRepositoryUrl(value: string): boolean {
  const url = value.trim();
  if (!url) {
    return false;
  }
  if (/^git@[^:]+:.+/.test(url)) {
    return true;
  }
  if (!/^https?:\/\/|^ssh:\/\//.test(url)) {
    return false;
  }
  try {
    const parsed = new URL(url);
    const segments = parsed.pathname.split("/").filter(Boolean);
    if (url.endsWith(".git")) {
      return true;
    }
    const hostedGitProviders = new Set(["github.com", "gitlab.com", "bitbucket.org", "dev.azure.com"]);
    return hostedGitProviders.has(parsed.hostname) && segments.length >= 2;
  } catch {
    return false;
  }
}

export function ProjectWizard({ open, onOpenChange }: ProjectWizardProps) {
  const router = useRouter();
  const createProject = useCreateProject();
  const { data: policyPacks, isLoading: policyPacksLoading } = usePolicyPacks();

  const [currentStep, setCurrentStep] = useState<WizardStep>("git");
  const [formData, setFormData] = useState({
    repoUrl: "",
    branch: "main",
    githubToken: "",
    projectClassification: "default",
    enforcementMode: "warn" as PolicyEnforcementMode,
    autoDiscovery: true,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const builtinPolicyPacks = useMemo(() => {
    const builtins = (policyPacks ?? []).filter((pack) => pack.is_builtin);
    return [...builtins].sort((a, b) => {
      const left = classificationRank.get(a.project_classification ?? "default") ?? Number.MAX_SAFE_INTEGER;
      const right = classificationRank.get(b.project_classification ?? "default") ?? Number.MAX_SAFE_INTEGER;
      return left - right;
    });
  }, [policyPacks]);

  const selectedPolicyPack =
    builtinPolicyPacks.find((pack) => pack.project_classification === formData.projectClassification) ??
    builtinPolicyPacks[0] ??
    null;

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep);

  const handleNext = () => {
    // Validation
    if (currentStep === "git") {
      if (!formData.repoUrl) {
        toast.error("Repository URL is required");
        return;
      }
      if (!looksLikeGitRepositoryUrl(formData.repoUrl)) {
        toast.error("Use a cloneable Git repository URL. Marketplace and docs pages will not onboard.");
        return;
      }
    }

    const nextIndex = currentStepIndex + 1;
    if (nextIndex < steps.length) {
      setCurrentStep(steps[nextIndex].id);
    } else {
      handleFinish();
    }
  };

  const handleBack = () => {
    const prevIndex = currentStepIndex - 1;
    if (prevIndex >= 0) {
      setCurrentStep(steps[prevIndex].id);
    }
  };

  const extractProjectName = (url: string) => {
    try {
      const parts = url.split("/");
      let name = parts[parts.length - 1];
      if (name.endsWith(".git")) {
        name = name.slice(0, -4);
      }
      return name || "untitled-project";
    } catch {
      return "untitled-project";
    }
  };

  const handleFinish = async () => {
    setIsSubmitting(true);
    try {
      const name = extractProjectName(formData.repoUrl);

      let onboardingQueued = true;
      let project = null;
      try {
        project = await createProject.mutateAsync({
          name,
          git_url: formData.repoUrl,
          github_token: formData.githubToken || undefined,
          base_branch: formData.branch || "main",
          project_classification: formData.projectClassification,
          policy_enforcement_mode: formData.enforcementMode,
          auto_onboard: true,
          auto_discovery: formData.autoDiscovery,
        });
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status === 503 &&
          (error.message || "").toLowerCase().includes("windmill integration not configured")
        ) {
          onboardingQueued = false;
        project = await createProject.mutateAsync({
          name,
          git_url: formData.repoUrl,
          github_token: formData.githubToken || undefined,
          base_branch: formData.branch || "main",
          project_classification: formData.projectClassification,
          policy_enforcement_mode: formData.enforcementMode,
          auto_onboard: false,
          auto_discovery: false,
        });
      } else {
        throw error;
        }
      }
      if (!project) {
        throw new Error("Project creation failed");
      }

      if (onboardingQueued) {
        toast.success("Project created and onboarding queued!");
      } else {
        toast.success(
          "Project created. Windmill not configured, so onboarding was not queued (start it from the Onboarding page)."
        );
      }
      onOpenChange(false);
      setCurrentStep("git");
      setFormData({
        repoUrl: "",
        branch: "main",
        githubToken: "",
        projectClassification: "default",
        enforcementMode: "warn",
        autoDiscovery: true,
      });

      // Redirect to the new project
      router.push(`/projects/${project.id}/onboarding`);
    } catch (error) {
      console.error(error);
      if (error instanceof ApiError) {
        toast.error(error.message || "Failed to create project");
      } else {
        toast.error("Failed to create project");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="3xl" className="flex max-h-[90vh] flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Follow the steps to set up your project with DevGodzilla.
          </DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center justify-between px-4 py-6">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const isCompleted = index < currentStepIndex;
            const isCurrent = step.id === currentStep;
            return (
              <div key={step.id} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                      isCompleted && "border-primary bg-primary text-primary-foreground",
                      isCurrent && "border-primary text-primary",
                      !isCompleted && !isCurrent && "border-muted text-muted-foreground"
                    )}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : (
                      <Icon className="h-5 w-5" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-xs font-medium",
                      isCurrent ? "text-foreground" : "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={cn(
                      "mx-2 flex-1 border-t-2",
                      isCompleted ? "border-primary" : "border-muted"
                    )}
                  />
                )}
              </div>
            );
          })}
        </div>

        <Separator />

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {currentStep === "git" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="repoUrl">Repository URL *</Label>
                <Input
                  id="repoUrl"
                  placeholder="https://github.com/username/repo.git"
                  value={formData.repoUrl}
                  onChange={(e) => setFormData({ ...formData, repoUrl: e.target.value })}
                />
                <p className="text-muted-foreground text-xs">
                  Enter the clone URL for your Git repository. Marketplace or documentation pages will not work here.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="branch">Default Branch</Label>
                <Input
                  id="branch"
                  placeholder="main"
                  value={formData.branch}
                  onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="githubToken">GitHub Token</Label>
                <Input
                  id="githubToken"
                  type="password"
                  placeholder="Optional: needed for private GitHub repositories"
                  value={formData.githubToken}
                  onChange={(e) => setFormData({ ...formData, githubToken: e.target.value })}
                />
                <p className="text-muted-foreground text-xs">
                  Leave blank for public repos. For private GitHub repositories, DevGodzilla uses
                  this token for clone, push, and pull request steps.
                </p>
              </div>
            </div>
          )}

          {currentStep === "policy" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="projectClassification">Project Classification</Label>
                <Select
                  value={formData.projectClassification}
                  onValueChange={(v) => setFormData({ ...formData, projectClassification: v })}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={
                        policyPacksLoading ? "Loading..." : "Select a project classification"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {builtinPolicyPacks.map((pack) => (
                      <SelectItem
                        key={`${pack.key}:${pack.version}`}
                        value={pack.project_classification || pack.key}
                      >
                        {pack.name}
                        {pack.description && (
                          <span className="text-muted-foreground ml-2">- {pack.description}</span>
                        )}
                      </SelectItem>
                    ))}
                    {builtinPolicyPacks.length === 0 && !policyPacksLoading && (
                      <SelectItem value="__no_policy_packs__" disabled>
                        No built-in policy packs available
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
                <p className="text-muted-foreground text-xs">
                  Choose the baseline governance model for this project.
                </p>
              </div>
              {selectedPolicyPack && (
                <div className="rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{selectedPolicyPack.name}</p>
                      <p className="text-muted-foreground mt-1 text-sm">
                        {selectedPolicyPack.description || "No description available."}
                      </p>
                    </div>
                    <Badge variant="secondary">
                      {selectedPolicyPack.key}@{selectedPolicyPack.version}
                    </Badge>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="enforcementMode">Enforcement Mode</Label>
                <Select
                  value={formData.enforcementMode}
                  onValueChange={(v) =>
                    setFormData({ ...formData, enforcementMode: v as PolicyEnforcementMode })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="off">Off (No policy checks)</SelectItem>
                    <SelectItem value="warn">Warn (Advisory only)</SelectItem>
                    <SelectItem value="block">Enforce (Block on violations)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {currentStep === "onboarding" && (
            <div className="space-y-4">
              <div className="bg-muted/50 rounded-lg border p-4">
                <h3 className="mb-2 font-medium">Project Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Repository:</span>
                    <span className="font-mono text-xs">{formData.repoUrl || "Not set"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Branch:</span>
                    <span>{formData.branch}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Classification:</span>
                    <span>{formData.projectClassification}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Policy Pack:</span>
                    <span>
                      {selectedPolicyPack
                        ? `${selectedPolicyPack.key}@${selectedPolicyPack.version}`
                        : "Unavailable"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">GitHub Token:</span>
                    <span>{formData.githubToken ? "Configured" : "Not set"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Enforcement:</span>
                    <Badge variant="secondary" className="capitalize">
                      {formData.enforcementMode}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Discovery:</span>
                    <span>{formData.autoDiscovery ? "Enabled" : "Disabled"}</span>
                  </div>
                </div>
              </div>
              <div className="rounded-lg border p-4">
                <div className="flex items-start gap-3">
                  <Checkbox
                    checked={formData.autoDiscovery}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, autoDiscovery: checked === true })
                    }
                  />
                  <div>
                    <p className="text-sm font-medium">Run repository discovery</p>
                    <p className="text-muted-foreground text-xs">
                      Generate discovery artifacts for planning and onboarding. Recommended.
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-lg border bg-blue-500/10 p-4">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  After creating the project, onboarding is queued in Windmill. You may need to
                  answer clarification questions to help DevGodzilla understand your codebase.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <Separator />
        <div className="flex justify-between px-6 py-4">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStepIndex === 0 || isSubmitting}
          >
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleNext} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {currentStepIndex === steps.length - 1 ? "Create Project" : "Next"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
