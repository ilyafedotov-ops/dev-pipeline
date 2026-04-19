"use client";

import { use, useState, useEffect, useCallback } from "react";
import Link from "next/link";

import {
  ArrowLeft,
  FileText,
  Hash,
  Loader2,
  RotateCcw,
  Save,
  AlertTriangle,
  Clock,
  Type,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  useConstitution,
  useConstitutionMetadata,
  useHasConstitution,
  useResetConstitution,
  useSaveConstitution,
} from "@/lib/api";
import {
  getConstitutionWordCount,
  estimateReadingTime,
  validateConstitutionContent,
} from "@/lib/api/hooks/use-constitution";

export default function ConstitutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = Number.parseInt(id, 10);

  const { data: constitution, isLoading: constitutionLoading } = useConstitution(projectId);
  const { data: metadata } = useConstitutionMetadata(projectId);
  const { hasConstitution } = useHasConstitution(projectId);
  const saveConstitution = useSaveConstitution();
  const resetConstitution = useResetConstitution();

  const [content, setContent] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  // Sync content from API
  useEffect(() => {
    if (constitution?.content !== undefined && !isDirty) {
      setContent(constitution.content);
    }
  }, [constitution?.content, isDirty]);

  const handleContentChange = useCallback(
    (value: string) => {
      setContent(value);
      setIsDirty(value !== (constitution?.content ?? ""));
    },
    [constitution?.content],
  );

  const handleSave = async () => {
    const validation = validateConstitutionContent(content);
    if (!validation.valid) {
      toast.error(validation.errors.join(", "));
      return;
    }
    if (validation.warnings.length > 0) {
      validation.warnings.forEach((w) => toast.warning(w));
    }
    try {
      await saveConstitution.mutateAsync({ projectId, content });
      setIsDirty(false);
      toast.success("Constitution saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save constitution");
    }
  };

  const handleReset = async () => {
    try {
      await resetConstitution.mutateAsync(projectId);
      setContent("");
      setIsDirty(false);
      setResetOpen(false);
      toast.success("Constitution reset to defaults");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reset constitution");
    }
  };

  const wordCount = getConstitutionWordCount(content);
  const readingTime = estimateReadingTime(content);
  const lineCount = content ? content.split("\n").length : 0;
  const charCount = content.length;
  const validation = validateConstitutionContent(content);

  if (constitutionLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50">
        <div className="container py-4">
          <Link
            href={`/projects/${projectId}`}
            className="text-muted-foreground hover:text-foreground mb-3 inline-flex items-center gap-1.5 text-sm transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Project
          </Link>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="h-6 w-6" />
              <div>
                <h1 className="text-xl font-bold tracking-tight">Constitution Editor</h1>
                <p className="text-muted-foreground text-sm">
                  Define project rules, coding standards, and architectural guidelines
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isDirty && (
                <Badge variant="destructive" className="text-xs">
                  Unsaved changes
                </Badge>
              )}
              {!hasConstitution && (
                <Badge variant="outline" className="text-xs">
                  No constitution set
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setResetOpen(true)}
                disabled={resetConstitution.isPending}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={saveConstitution.isPending || !isDirty}
              >
                {saveConstitution.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_300px]">
          {/* Editor */}
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">Constitution Content</CardTitle>
                  <div className="text-muted-foreground flex items-center gap-3 text-xs">
                    <span>{lineCount} lines</span>
                    <Separator orientation="vertical" className="h-3" />
                    <span>{charCount.toLocaleString()} chars</span>
                  </div>
                </div>
                <CardDescription>
                  Write in Markdown. This file guides all AI agents working on the project.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={content}
                  onChange={(e) => handleContentChange(e.target.value)}
                  placeholder={`# Project Constitution\n\n## Coding Standards\n- Use TypeScript for all new files\n- Follow ESLint configuration\n\n## Architecture\n- Follow clean architecture patterns\n- Use dependency injection\n\n## Testing\n- Write unit tests for all business logic\n- Maintain >80% code coverage`}
                  className="min-h-[500px] resize-y font-mono text-sm leading-relaxed"
                />
              </CardContent>
            </Card>

            {/* Validation */}
            {content && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Validation</CardTitle>
                </CardHeader>
                <CardContent>
                  {validation.valid ? (
                    <div className="flex items-center gap-2 text-sm text-green-600">
                      <div className="h-2 w-2 rounded-full bg-green-500" />
                      Constitution is valid
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {validation.errors.map((err, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm text-destructive">
                          <AlertTriangle className="h-3 w-3" />
                          {err}
                        </div>
                      ))}
                    </div>
                  )}
                  {validation.warnings.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {validation.warnings.map((w, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm text-amber-600">
                          <AlertTriangle className="h-3 w-3" />
                          {w}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar: Metadata */}
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Metadata</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <Type className="text-muted-foreground h-4 w-4" />
                  <div>
                    <div className="text-muted-foreground text-xs">Word Count</div>
                    <div className="text-sm font-medium">{wordCount.toLocaleString()}</div>
                  </div>
                </div>
                <Separator />
                <div className="flex items-center gap-3">
                  <Clock className="text-muted-foreground h-4 w-4" />
                  <div>
                    <div className="text-muted-foreground text-xs">Reading Time</div>
                    <div className="text-sm font-medium">~{readingTime} min</div>
                  </div>
                </div>
                <Separator />
                <div className="flex items-center gap-3">
                  <FileText className="text-muted-foreground h-4 w-4" />
                  <div>
                    <div className="text-muted-foreground text-xs">Lines</div>
                    <div className="text-sm font-medium">{lineCount.toLocaleString()}</div>
                  </div>
                </div>
                <Separator />
                <div className="flex items-center gap-3">
                  <Hash className="text-muted-foreground h-4 w-4" />
                  <div>
                    <div className="text-muted-foreground text-xs">Characters</div>
                    <div className="text-sm font-medium">{charCount.toLocaleString()}</div>
                  </div>
                </div>
                {metadata?.hash && (
                  <>
                    <Separator />
                    <div>
                      <div className="text-muted-foreground text-xs">Content Hash</div>
                      <code className="mt-1 block text-xs break-all">{metadata.hash}</code>
                    </div>
                  </>
                )}
                {metadata?.version && (
                  <>
                    <Separator />
                    <div>
                      <div className="text-muted-foreground text-xs">Version</div>
                      <div className="text-sm font-medium">{metadata.version}</div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Tips</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-muted-foreground space-y-2 text-xs">
                  <li>• Use <code className="bg-muted rounded px-1"># headers</code> to organize sections</li>
                  <li>• Include coding, architecture, and testing guidelines</li>
                  <li>• Reference specific tools, frameworks, and versions</li>
                  <li>• Define naming conventions and file structure</li>
                  <li>• All AI agents working on the project will follow these rules</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Reset Confirmation */}
      <ConfirmDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        title="Reset Constitution"
        description="This will clear all constitution content and reset to defaults. This action cannot be undone."
        confirmText="Reset"
        variant="destructive"
        onConfirm={handleReset}
      />
    </div>
  );
}
