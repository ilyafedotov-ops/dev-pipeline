"use client";

import { use, useCallback,useState } from "react";
import Link from "next/link";

import {
  ArrowLeft,
  Clock,
  FileText,
  Hash,
  RotateCcw,
  Type,
} from "lucide-react";
import { toast } from "sonner";

import { ConstitutionEditor } from "@/components/features/constitution-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Separator } from "@/components/ui/separator";
import {
  useConstitution,
  useConstitutionMetadata,
  useHasConstitution,
  useResetConstitution,
} from "@/lib/api";
import {
  estimateReadingTime,
  getConstitutionWordCount,
} from "@/lib/api/hooks/use-constitution";

export default function ConstitutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = Number.parseInt(id, 10);

  const { data: constitution } = useConstitution(projectId);
  const { data: metadata } = useConstitutionMetadata(projectId);
  const { hasConstitution } = useHasConstitution(projectId);
  const resetConstitution = useResetConstitution();

  const [resetOpen, setResetOpen] = useState(false);

  const content = constitution?.content ?? "";
  const wordCount = getConstitutionWordCount(content);
  const readingTime = estimateReadingTime(content);
  const lineCount = content ? content.split("\n").length : 0;
  const charCount = content.length;

  const handleReset = async () => {
    try {
      await resetConstitution.mutateAsync(projectId);
      setResetOpen(false);
      toast.success("Constitution reset to defaults");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reset constitution");
    }
  };

  const handleSaveSuccess = useCallback(() => {
    toast.success("Constitution saved");
  }, []);

  const handleSaveError = useCallback((error: Error) => {
    toast.error(error.message);
  }, []);

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
            </div>
          </div>
        </div>
      </div>

      <div className="container py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_300px]">
          {/* Editor — uses ConstitutionEditor component with article CRUD mode */}
          <ConstitutionEditor
            projectId={projectId}
            onSaveSuccess={handleSaveSuccess}
            onSaveError={handleSaveError}
          />

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
