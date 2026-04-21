"use client";

import React, { useCallback, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
  GripVertical,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Trash2,
} from "lucide-react";
import remarkGfm from "remark-gfm";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useConstitution,
  useConstitutionMetadata,
  useSaveConstitution,
  useValidateConstitution,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface ConstitutionEditorProps {
  projectId: number;
  className?: string;
  onSaveSuccess?: () => void;
  onSaveError?: (error: Error) => void;
}

export interface ConstitutionData {
  content: string;
  hash?: string | null;
  version?: string | null;
}

export interface ConstitutionArticle {
  id: string;
  title: string;
  level: number; // 1-6 for h1-h6
  content: string; // Markdown content of the article body
  order: number;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Validates constitution content for basic structure
 */
export function validateConstitution(content: string): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!content.trim()) {
    return { valid: true, errors: [] }; // Empty is valid (will use defaults)
  }

  const lines = content.split("\n");
  const hasHeaders = lines.some((line) => line.startsWith("#"));

  if (!hasHeaders) {
    errors.push("Constitution should contain at least one header (# Title)");
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Parse markdown content into structured articles (sections delimited by headers)
 */
export function parseArticles(content: string): ConstitutionArticle[] {
  if (!content.trim()) return [];

  const lines = content.split("\n");
  const articles: ConstitutionArticle[] = [];
  let currentArticle: ConstitutionArticle | null = null;
  let order = 0;

  for (const line of lines) {
    const headerMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headerMatch) {
      if (currentArticle) {
        articles.push(currentArticle);
      }
      currentArticle = {
        id: `article-${order}`,
        title: headerMatch[2].trim(),
        level: headerMatch[1].length,
        content: "",
        order,
      };
      order++;
    } else if (currentArticle) {
      currentArticle.content += (currentArticle.content ? "\n" : "") + line;
    }
  }

  if (currentArticle) {
    articles.push(currentArticle);
  }

  return articles;
}

/**
 * Serialize articles back to markdown content
 */
export function serializeArticles(articles: ConstitutionArticle[]): string {
  return articles
    .map((article) => {
      const prefix = "#".repeat(article.level);
      const body = article.content.trim();
      return `${prefix} ${article.title}${body ? `\n\n${  body}` : ""}`;
    })
    .join("\n\n");
}

/**
 * Truncates content for preview
 */
export function truncatePreview(content: string, maxLength: number = 200): string {
  if (content.length <= maxLength) return content;
  return `${content.slice(0, maxLength)}...`;
}

// =============================================================================
// Article Editor Component
// =============================================================================

interface ArticleEditorProps {
  article: ConstitutionArticle;
  onUpdate: (updated: ConstitutionArticle) => void;
  onDelete: () => void;
  isEditing: boolean;
  onStartEdit: () => void;
  onCancel: () => void;
}

function ArticleEditor({ article, onUpdate, onDelete, isEditing, onStartEdit, onCancel }: ArticleEditorProps) {
  const [draft, setDraft] = useState<ConstitutionArticle>({ ...article });

  const handleSave = useCallback(() => {
    onUpdate(draft);
  }, [draft, onUpdate]);

  React.useEffect(() => {
    if (isEditing) {
      setDraft({ ...article });
    }
  }, [isEditing, article]);

  return (
    <div className="group border-l-2 border-muted py-3 pl-4 pr-2 transition-colors hover:border-primary/50">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-xs font-mono">{"#".repeat(article.level)}</span>
                <Input
                  value={draft.title}
                  onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                  className="h-8 text-sm font-semibold"
                  placeholder="Article title..."
                />
              </div>
              <Textarea
                value={draft.content}
                onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))}
                className="min-h-[120px] font-mono text-sm"
                placeholder="Article content in markdown..."
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSave}>
                  <Save className="mr-1 h-3 w-3" /> Save
                </Button>
                <Button size="sm" variant="outline" onClick={onCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <GripVertical className="text-muted-foreground h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
                <h4
                  className={cn(
                    "font-semibold",
                    article.level === 1 && "text-lg",
                    article.level === 2 && "text-base",
                    article.level === 3 && "text-sm",
                    article.level >= 4 && "text-xs",
                  )}
                >
                  {article.title}
                </h4>
                <Badge variant="secondary" className="text-[10px]">
                  H{article.level}
                </Badge>
              </div>
              {article.content.trim() && (
                <div className="text-muted-foreground mt-2 max-h-[100px] overflow-hidden text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {truncatePreview(article.content.trim(), 300)}
                  </ReactMarkdown>
                </div>
              )}
            </>
          )}
        </div>

        {!isEditing && (
          <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onStartEdit}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="text-destructive h-7 w-7" onClick={onDelete}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function ConstitutionEditor({
  projectId,
  className,
  onSaveSuccess,
  onSaveError,
}: ConstitutionEditorProps) {
  const { data, isLoading, error } = useConstitution(projectId);
  const { data: metadata } = useConstitutionMetadata(projectId);
  const saveMutation = useSaveConstitution();
  const validateMutation = useValidateConstitution();

  const [editedContent, setEditedContent] = useState<string>("");
  const [mode, setMode] = useState<"preview" | "editor">("preview");
  const [editingArticleId, setEditingArticleId] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [expandedArticles, setExpandedArticles] = useState<Set<string>>(new Set());

  const content = data?.content ?? "";
  const articles = useMemo(() => parseArticles(content), [content]);

  const handleStartRawEdit = useCallback(() => {
    setEditedContent(content);
    setMode("editor");
    setLocalError(null);
  }, [content]);

  const handleCancelRawEdit = useCallback(() => {
    setEditedContent("");
    setMode("preview");
    setLocalError(null);
  }, []);

  const handleSaveRaw = useCallback(async () => {
    const validation = validateConstitution(editedContent);
    if (!validation.valid) {
      setLocalError(validation.errors.join(", "));
      return;
    }

    try {
      await saveMutation.mutateAsync({ projectId, content: editedContent });
      setMode("preview");
      setEditedContent("");
      setLocalError(null);
      onSaveSuccess?.();
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Failed to save constitution");
      setLocalError(error.message);
      onSaveError?.(error);
    }
  }, [editedContent, projectId, saveMutation, onSaveSuccess, onSaveError]);

  const handleArticleUpdate = useCallback(
    async (updated: ConstitutionArticle) => {
      const newArticles = articles.map((a) => (a.id === updated.id ? updated : a));
      const newContent = serializeArticles(newArticles);
      try {
        await saveMutation.mutateAsync({ projectId, content: newContent });
        setEditingArticleId(null);
        onSaveSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Failed to update article");
        setLocalError(error.message);
        onSaveError?.(error);
      }
    },
    [articles, projectId, saveMutation, onSaveSuccess, onSaveError],
  );

  const handleArticleDelete = useCallback(
    async (articleId: string) => {
      const newArticles = articles.filter((a) => a.id !== articleId);
      const newContent = serializeArticles(newArticles);
      try {
        await saveMutation.mutateAsync({ projectId, content: newContent });
        onSaveSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Failed to delete article");
        setLocalError(error.message);
        onSaveError?.(error);
      }
    },
    [articles, projectId, saveMutation, onSaveSuccess, onSaveError],
  );

  const handleAddArticle = useCallback(() => {
    const newArticle: ConstitutionArticle = {
      id: `article-${Date.now()}`,
      title: "New Article",
      level: 2,
      content: "",
      order: articles.length,
    };
    const newArticles = [...articles, newArticle];
    const newContent = serializeArticles(newArticles);
    saveMutation.mutate(
      { projectId, content: newContent },
      {
        onSuccess: () => {
          setEditingArticleId(newArticle.id);
          onSaveSuccess?.();
        },
        onError: (err) => {
          setLocalError(err instanceof Error ? err.message : "Failed to add article");
        },
      },
    );
  }, [articles, projectId, saveMutation, onSaveSuccess]);

  const handleReset = useCallback(async () => {
    try {
      await saveMutation.mutateAsync({ projectId, content: "" });
      setLocalError(null);
      setMode("preview");
      onSaveSuccess?.();
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Failed to reset constitution");
      setLocalError(error.message);
      onSaveError?.(error);
    }
  }, [projectId, saveMutation, onSaveSuccess, onSaveError]);

  const toggleArticleExpanded = useCallback((id: string) => {
    setExpandedArticles((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  if (isLoading) {
    return <LoadingState message="Loading constitution..." />;
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading constitution"
        description={error instanceof Error ? error.message : "An unknown error occurred"}
      />
    );
  }

  const validation = mode === "editor" ? validateConstitution(editedContent) : { valid: true, errors: [] };
  const hasChanges = mode === "editor" && editedContent !== content;

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Constitution
            </CardTitle>
            <CardDescription>
              Define project-specific guidelines, coding standards, and preferences
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {data?.content && metadata && (
              <Badge variant="secondary" className="text-xs">
                {metadata.line_count} lines
              </Badge>
            )}
            {data?.content && (
              <Badge variant="outline" className="text-xs">
                {articles.length} articles
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Error display */}
        {(localError || saveMutation.error) && (
          <div className="bg-destructive/10 text-destructive flex items-start gap-2 rounded-md p-3 text-sm">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              {localError ||
                (saveMutation.error instanceof Error
                  ? saveMutation.error.message
                  : "An error occurred")}
            </span>
          </div>
        )}

        {/* Validation warnings */}
        {!validation.valid && (
          <div className="rounded-md bg-yellow-500/10 p-3 text-sm text-yellow-600 dark:text-yellow-400">
            {validation.errors.join(", ")}
          </div>
        )}

        {mode === "editor" ? (
          /* ===========================
           * Raw Markdown Editor Mode
           * =========================== */
          <div className="space-y-4">
            <Tabs defaultValue="write">
              <TabsList>
                <TabsTrigger value="write">
                  <Pencil className="mr-1 h-3.5 w-3.5" />
                  Write
                </TabsTrigger>
                <TabsTrigger value="preview">
                  <Eye className="mr-1 h-3.5 w-3.5" />
                  Preview
                </TabsTrigger>
              </TabsList>
              <TabsContent value="write">
                <Textarea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  placeholder={
                    "# Project Constitution\n\nDefine your project's coding standards, architectural guidelines, and preferences here...\n\n## Coding Standards\n- Use TypeScript strict mode\n- Prefer functional components over class components\n\n## Architecture\n- Follow hexagonal architecture principles\n- Keep business logic separate from infrastructure"
                  }
                  className="min-h-[400px] font-mono text-sm"
                />
              </TabsContent>
              <TabsContent value="preview">
                <div className="bg-muted/30 rounded-md border p-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    {editedContent.trim() ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{editedContent}</ReactMarkdown>
                    ) : (
                      <p className="text-muted-foreground italic">Nothing to preview</p>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex items-center justify-between">
              <p className="text-muted-foreground text-xs">
                {editedContent.length} characters • {editedContent.split("\n").length} lines •{" "}
                {editedContent.trim() ? editedContent.trim().split(/\s+/).length : 0} words
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleCancelRawEdit} disabled={saveMutation.isPending}>
                  Cancel
                </Button>
                <Button onClick={handleSaveRaw} disabled={saveMutation.isPending || !hasChanges}>
                  {saveMutation.isPending ? (
                    "Saving..."
                  ) : (
                    <>
                      <Save className="mr-1 h-4 w-4" />
                      Save Changes
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          /* ===========================
           * Article Preview & CRUD Mode
           * =========================== */
          <div className="space-y-4">
            {articles.length > 0 ? (
              <>
                {/* Full markdown preview */}
                <div className="bg-muted/30 rounded-md border p-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none max-h-[300px] overflow-auto">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                  </div>
                </div>

                {/* Article list with CRUD */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium">Articles ({articles.length})</h3>
                    <Button variant="outline" size="sm" onClick={handleAddArticle}>
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add Article
                    </Button>
                  </div>

                  <div className="divide-y">
                    {articles.map((article) => {
                      const isExpanded = expandedArticles.has(article.id);
                      const isEditing = editingArticleId === article.id;

                      return (
                        <div key={article.id}>
                          <ArticleEditor
                            article={article}
                            isEditing={isEditing}
                            onStartEdit={() => setEditingArticleId(article.id)}
                            onCancel={() => setEditingArticleId(null)}
                            onUpdate={handleArticleUpdate}
                            onDelete={() => handleArticleDelete(article.id)}
                          />
                          {article.content.trim() && !isEditing && (
                            <button
                              className="text-muted-foreground hover:text-foreground ml-9 mt-1 flex items-center gap-1 text-xs transition-colors"
                              onClick={() => toggleArticleExpanded(article.id)}
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-3 w-3" />
                              ) : (
                                <ChevronRight className="h-3 w-3" />
                              )}
                              {isExpanded ? "Collapse" : "Expand full content"}
                            </button>
                          )}
                          {isExpanded && !isEditing && article.content.trim() && (
                            <div className="ml-9 mt-2 rounded-md border p-3">
                              <div className="prose prose-sm dark:prose-invert max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {article.content.trim()}
                                </ReactMarkdown>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-md border border-dashed p-8 text-center">
                <FileText className="text-muted-foreground mx-auto mb-2 h-10 w-10" />
                <p className="text-muted-foreground">No constitution defined yet.</p>
                <p className="text-muted-foreground mt-1 text-xs">
                  Click &quot;Edit&quot; to add project-specific guidelines using markdown articles.
                </p>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center justify-end gap-2">
              {content && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleReset}
                  disabled={saveMutation.isPending}
                  className="text-muted-foreground"
                >
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Reset
                </Button>
              )}
              <Button onClick={handleStartRawEdit} disabled={saveMutation.isPending}>
                {content ? "Edit Raw Markdown" : "Create Constitution"}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
