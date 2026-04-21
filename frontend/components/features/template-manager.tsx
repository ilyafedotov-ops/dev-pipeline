"use client";

import { useCallback, useMemo, useState } from "react";

import {
  AlertCircle,
  CheckSquare,
  Copy,
  Download,
  Edit,
  Eye,
  FileText,
  ListTodo,
  Plus,
  Search,
  Trash2,
  Workflow,
} from "lucide-react";

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
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  generateTemplateId,
  type Template,
  type TemplateCreate,
  type TemplateUpdate,
  useCreateTemplate,
  useDeleteTemplate,
  useDuplicateTemplate,
  useRenderTemplate,
  useTemplate,
  useTemplates,
  useUpdateTemplate,
  validateTemplateId,
} from "@/lib/api/hooks/use-templates";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface TemplateManagerProps {
  className?: string;
  defaultCategory?: string;
  onTemplateSelect?: (template: Template) => void;
  onSelectMode?: boolean;
}

export interface TemplateListProps {
  category?: string;
  search?: string;
  onSelect?: (template: Template) => void;
  onSelectMode?: boolean;
  selectedId?: string;
}

export interface TemplateEditorProps {
  templateId?: string;
  onSave?: (template: Template) => void;
  onCancel?: () => void;
}

export interface TemplatePreviewProps {
  templateId: string;
  variables?: Record<string, unknown>;
}

// =============================================================================
// Category Icons
// =============================================================================

function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const icons: Record<string, typeof FileText> = {
    specification: FileText,
    plan: ListTodo,
    protocol: Workflow,
    checklist: CheckSquare,
  };
  const Icon = icons[category] || FileText;
  return <Icon className={className} />;
}

// =============================================================================
// Template List Component
// =============================================================================

export function TemplateList({
  category,
  search,
  onSelect,
  onSelectMode,
  selectedId,
}: TemplateListProps) {
  const { data, isLoading, error } = useTemplates({ category, search });

  if (isLoading) {
    return <LoadingState message="Loading templates..." />;
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading templates"
        description={error instanceof Error ? error.message : "An unknown error occurred"}
      />
    );
  }

  if (!data?.items?.length) {
    return (
      <EmptyState
        icon={FileText}
        title="No templates found"
        description={
          search ? `No templates match "${search}"` : "Create your first template to get started"
        }
      />
    );
  }

  return (
    <div className="space-y-2">
      {data.items.map((template) => (
        <Card
          key={template.id}
          className={cn(
            "hover:border-primary/50 cursor-pointer transition-colors",
            selectedId === template.id && "border-primary bg-primary/5"
          )}
          onClick={() => onSelect?.(template)}
        >
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <CategoryIcon
                  category={template.category}
                  className="text-muted-foreground mt-0.5 h-5 w-5 shrink-0"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-medium">{template.name}</h3>
                    {template.is_default && (
                      <Badge variant="secondary" className="text-xs">
                        Default
                      </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground truncate text-sm">
                    {template.description || template.id}
                  </p>
                </div>
              </div>
              {onSelectMode && (
                <Button variant="ghost" size="sm">
                  Select
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// =============================================================================
// Template Editor Component
// =============================================================================

export function TemplateEditor({ templateId, onSave, onCancel }: TemplateEditorProps) {
  const { data: existingTemplate, isLoading } = useTemplate(templateId || "");
  const createMutation = useCreateTemplate();
  const updateMutation = useUpdateTemplate();

  const [formData, setFormData] = useState<TemplateCreate>({
    id: "",
    name: "",
    description: "",
    category: "specification",
    content: "",
    variables: {},
  });
  const [idError, setIdError] = useState<string | null>(null);

  // Initialize form when existing template loads
  useState(() => {
    if (existingTemplate) {
      setFormData({
        id: existingTemplate.id,
        name: existingTemplate.name,
        description: existingTemplate.description,
        category: existingTemplate.category,
        content: existingTemplate.content,
        variables: existingTemplate.variables,
      });
    }
  });

  const isEditing = !!templateId;
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleIdChange = useCallback((value: string) => {
    setFormData((prev) => ({ ...prev, id: value }));
    const validation = validateTemplateId(value);
    setIdError(validation.valid ? null : validation.error || null);
  }, []);

  const handleNameChange = useCallback(
    (value: string) => {
      setFormData((prev) => {
        const updates = { ...prev, name: value };
        // Auto-generate ID if creating new and ID is empty
        if (!templateId && !prev.id) {
          updates.id = generateTemplateId(value);
        }
        return updates;
      });
    },
    [templateId]
  );

  const handleSubmit = useCallback(async () => {
    if (!isEditing && idError) {
      return;
    }

    try {
      let result: Template;
      if (isEditing) {
        const updates: TemplateUpdate = {
          name: formData.name,
          description: formData.description,
          category: formData.category,
          content: formData.content,
          variables: formData.variables,
        };
        result = await updateMutation.mutateAsync({
          id: templateId!,
          updates,
        });
      } else {
        result = await createMutation.mutateAsync(formData);
      }
      onSave?.(result);
    } catch (error) {
      console.error("Failed to save template:", error);
    }
  }, [formData, isEditing, templateId, idError, createMutation, updateMutation, onSave]);

  if (isLoading) {
    return <LoadingState message="Loading template..." />;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label className="text-sm font-medium">Name</Label>
          <Input
            value={formData.name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Template name"
          />
        </div>

        {!isEditing && (
          <div className="grid gap-2">
            <Label className="text-sm font-medium">ID</Label>
            <Input
              value={formData.id}
              onChange={(e) => handleIdChange(e.target.value)}
              placeholder="template-id"
              className={idError ? "border-destructive" : ""}
            />
            {idError && <p className="text-destructive text-xs">{idError}</p>}
          </div>
        )}

        <div className="grid gap-2">
          <Label className="text-sm font-medium">Category</Label>
          <Select
            value={formData.category}
            onValueChange={(value) =>
              setFormData((prev) => ({
                ...prev,
                category: value as TemplateCreate["category"],
              }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="specification">Specification</SelectItem>
              <SelectItem value="plan">Plan</SelectItem>
              <SelectItem value="protocol">Protocol</SelectItem>
              <SelectItem value="checklist">Checklist</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <Label className="text-sm font-medium">Description</Label>
          <Input
            value={formData.description}
            onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
            placeholder="Brief description of the template"
          />
        </div>

        <div className="grid gap-2">
          <Label className="text-sm font-medium">Content</Label>
          <Textarea
            value={formData.content}
            onChange={(e) => setFormData((prev) => ({ ...prev, content: e.target.value }))}
            placeholder="# Template Content&#10;&#10;Use {variable_name} for placeholders"
            className="min-h-[300px] font-mono text-sm"
          />
          <p className="text-muted-foreground text-xs">
            Use {"{variable_name}"} syntax for variables
          </p>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={isPending || !!idError}>
          {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Template Preview Component
// =============================================================================

export function TemplatePreview({ templateId, variables = {} }: TemplatePreviewProps) {
  const { data: template, isLoading } = useTemplate(templateId);
  const renderMutation = useRenderTemplate();

  const renderedContent = useMemo(() => {
    if (!template) return "";

    // If variables provided, render server-side
    if (Object.keys(variables).length > 0) {
      renderMutation.mutate({ templateId, variables });
      return null;
    }

    // Otherwise show raw template
    return template.content;
  }, [template, templateId, variables]);

  if (isLoading) {
    return <LoadingState message="Loading preview..." />;
  }

  if (!template) {
    return (
      <EmptyState
        icon={Eye}
        title="No template selected"
        description="Select a template to preview"
      />
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Eye className="h-5 w-5" />
          Preview: {template.name}
        </CardTitle>
        <CardDescription>{template.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <pre className="bg-muted/30 max-h-[400px] overflow-auto rounded-md p-4 font-mono text-sm whitespace-pre-wrap">
          {renderMutation.data?.content || renderedContent}
        </pre>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Main Template Manager Component
// =============================================================================

export function TemplateManager({
  className,
  defaultCategory,
  onTemplateSelect,
  onSelectMode,
}: TemplateManagerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>(defaultCategory || "all");
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const deleteMutation = useDeleteTemplate();
  const duplicateMutation = useDuplicateTemplate();

  const handleSelectTemplate = useCallback(
    (template: Template) => {
      if (onSelectMode) {
        onTemplateSelect?.(template);
      } else {
        setSelectedTemplate(template);
        setIsEditing(false);
      }
    },
    [onSelectMode, onTemplateSelect]
  );

  const handleEdit = useCallback(() => {
    setIsEditing(true);
  }, []);

  const handleDuplicate = useCallback(async () => {
    if (!selectedTemplate) return;

    try {
      const newId = `${selectedTemplate.id}-copy`;
      await duplicateMutation.mutateAsync({
        templateId: selectedTemplate.id,
        newId,
        newName: `${selectedTemplate.name} (Copy)`,
      });
    } catch (error) {
      console.error("Failed to duplicate template:", error);
    }
  }, [selectedTemplate, duplicateMutation]);

  const handleDelete = useCallback(async () => {
    if (!selectedTemplate) return;

    try {
      await deleteMutation.mutateAsync(selectedTemplate.id);
      setShowDeleteDialog(false);
      setSelectedTemplate(null);
    } catch (error) {
      console.error("Failed to delete template:", error);
    }
  }, [selectedTemplate, deleteMutation]);

  const _handleCloseDetail = useCallback(() => {
    setSelectedTemplate(null);
    setIsEditing(false);
    setIsCreating(false);
  }, []);

  return (
    <div className={cn("grid gap-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Templates</h2>
          <p className="text-muted-foreground">
            Manage reusable templates for specifications, plans, and protocols
          </p>
        </div>
        {!onSelectMode && (
          <Button onClick={() => setIsCreating(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Template
          </Button>
        )}
      </div>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-[1fr,400px]">
        {/* Left: List */}
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
              <Input
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="specification">Specifications</SelectItem>
                <SelectItem value="plan">Plans</SelectItem>
                <SelectItem value="protocol">Protocols</SelectItem>
                <SelectItem value="checklist">Checklists</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* List */}
          <TemplateList
            category={selectedCategory === "all" ? undefined : selectedCategory}
            search={searchQuery || undefined}
            onSelect={handleSelectTemplate}
            onSelectMode={onSelectMode}
            selectedId={selectedTemplate?.id}
          />
        </div>

        {/* Right: Detail / Editor */}
        <div>
          {isCreating ? (
            <Card>
              <CardHeader>
                <CardTitle>Create Template</CardTitle>
                <CardDescription>Create a new reusable template</CardDescription>
              </CardHeader>
              <CardContent>
                <TemplateEditor
                  onSave={() => {
                    setIsCreating(false);
                  }}
                  onCancel={() => setIsCreating(false)}
                />
              </CardContent>
            </Card>
          ) : selectedTemplate ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CategoryIcon category={selectedTemplate.category} className="h-5 w-5" />
                    <CardTitle>{isEditing ? "Edit Template" : selectedTemplate.name}</CardTitle>
                  </div>
                  {selectedTemplate.is_default && <Badge variant="secondary">Default</Badge>}
                </div>
                <CardDescription>
                  {isEditing ? `Editing ${selectedTemplate.id}` : selectedTemplate.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {isEditing ? (
                  <TemplateEditor
                    templateId={selectedTemplate.id}
                    onSave={() => {
                      setIsEditing(false);
                    }}
                    onCancel={() => setIsEditing(false)}
                  />
                ) : (
                  <>
                    {/* Preview */}
                    <div>
                      <Label className="mb-2 block text-sm font-medium">Content Preview</Label>
                      <pre className="bg-muted/30 max-h-[300px] overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
                        {selectedTemplate.content}
                      </pre>
                    </div>

                    {/* Variables */}
                    {Object.keys(selectedTemplate.variables).length > 0 && (
                      <div>
                        <Label className="mb-2 block text-sm font-medium">Variables</Label>
                        <div className="space-y-2">
                          {Object.entries(selectedTemplate.variables).map(([name, config]) => (
                            <div key={name} className="flex items-center justify-between text-sm">
                              <span className="font-mono">{name}</span>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">
                                  {config.type}
                                </Badge>
                                {config.required && (
                                  <Badge variant="destructive" className="text-xs">
                                    Required
                                  </Badge>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2 border-t pt-4">
                      <Button variant="outline" size="sm" onClick={handleEdit}>
                        <Edit className="mr-1 h-4 w-4" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleDuplicate}
                        disabled={duplicateMutation.isPending}
                      >
                        <Copy className="mr-1 h-4 w-4" />
                        Duplicate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          // Export logic
                          window.open(`/templates/${selectedTemplate.id}/export`, "_blank");
                        }}
                      >
                        <Download className="mr-1 h-4 w-4" />
                        Export
                      </Button>
                      {!selectedTemplate.is_default && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setShowDeleteDialog(true)}
                        >
                          <Trash2 className="mr-1 h-4 w-4" />
                          Delete
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-8">
                <EmptyState
                  icon={FileText}
                  title="No template selected"
                  description="Select a template from the list to view details"
                />
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Template</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{selectedTemplate?.name}"? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default TemplateManager;
