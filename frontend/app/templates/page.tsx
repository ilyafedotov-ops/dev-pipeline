"use client";

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";
import {
  CheckSquare,
  Copy,
  Download,
  Eye,
  FileText,
  ListTodo,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  Workflow,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, DeleteConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable } from "@/components/ui/data-table";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  generateTemplateId,
  getCategoryDisplayName,
  type Template,
  type TemplateCreate,
  type TemplateUpdate,
  useCreateTemplate,
  useDeleteTemplate,
  useDuplicateTemplate,
  useExportTemplate,
  useImportTemplate,
  useRenderTemplate,
  useTemplate,
  useTemplateCategories,
  useTemplates,
  useUpdateTemplate,
  validateTemplateId,
} from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

// ─── Category icon mapping ───────────────────────────────────────────────────

const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  specification: FileText,
  plan: ListTodo,
  protocol: Workflow,
  checklist: CheckSquare,
};

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function TemplatesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Data
  const {
    data: templatesData,
    isLoading,
    refetch,
  } = useTemplates({
    category: selectedCategory ?? undefined,
    search: searchQuery || undefined,
  });
  const { data: categoriesData } = useTemplateCategories();
  const { data: selectedTemplate } = useTemplate(selectedTemplateId ?? "");

  // Mutations
  const createTemplate = useCreateTemplate();
  const updateTemplate = useUpdateTemplate();
  const deleteTemplate = useDeleteTemplate();
  const duplicateTemplate = useDuplicateTemplate();
  const renderTemplate = useRenderTemplate();
  const exportTemplate = useExportTemplate();
  const importTemplate = useImportTemplate();

  const templates = templatesData?.items ?? [];

  // ─── Preview state ────────────────────────────────────────────────────────
  const [previewVariables, setPreviewVariables] = useState<Record<string, string>>({});
  const [renderedContent, setRenderedContent] = useState<string | null>(null);

  const selectedTemplateVars = useMemo(() => {
    if (!selectedTemplate?.variables) return {};
    return selectedTemplate.variables;
  }, [selectedTemplate]);

  const handlePreviewRender = async () => {
    if (!selectedTemplateId) return;
    try {
      const result = await renderTemplate.mutateAsync({
        templateId: selectedTemplateId,
        variables: previewVariables,
      });
      setRenderedContent(result.content);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to render template");
    }
  };

  // ─── Create state ─────────────────────────────────────────────────────────
  const [createForm, setCreateForm] = useState<TemplateCreate>({
    id: "",
    name: "",
    description: "",
    category: "specification",
    content: "",
  });

  const handleCreate = async () => {
    const idValidation = validateTemplateId(createForm.id);
    if (!idValidation.valid) {
      toast.error(idValidation.error);
      return;
    }
    try {
      await createTemplate.mutateAsync(createForm);
      setCreateOpen(false);
      setCreateForm({ id: "", name: "", description: "", category: "specification", content: "" });
      toast.success("Template created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create template");
    }
  };

  // ─── Edit state ───────────────────────────────────────────────────────────
  const [editForm, setEditForm] = useState<TemplateUpdate>({});

  const openEdit = (template: Template) => {
    setEditForm({
      name: template.name,
      description: template.description,
      category: template.category,
      content: template.content,
    });
    setSelectedTemplateId(template.id);
    setEditOpen(true);
  };

  const handleEdit = async () => {
    if (!selectedTemplateId) return;
    try {
      await updateTemplate.mutateAsync({ id: selectedTemplateId, updates: editForm });
      setEditOpen(false);
      toast.success("Template updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update template");
    }
  };

  // ─── Duplicate state ──────────────────────────────────────────────────────
  const [dupId, setDupId] = useState("");
  const [dupName, setDupName] = useState("");

  const openDuplicate = (template: Template) => {
    setSelectedTemplateId(template.id);
    setDupId(generateTemplateId(`${template.id}-copy`));
    setDupName(`${template.name} (Copy)`);
    setDuplicateOpen(true);
  };

  const handleDuplicate = async () => {
    if (!selectedTemplateId || !dupId) return;
    try {
      await duplicateTemplate.mutateAsync({
        templateId: selectedTemplateId,
        newId: dupId,
        newName: dupName || undefined,
      });
      setDuplicateOpen(false);
      toast.success("Template duplicated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to duplicate template");
    }
  };

  // ─── Delete ───────────────────────────────────────────────────────────────
  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteTemplate.mutateAsync(deleteId);
      setDeleteId(null);
      toast.success("Template deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete template");
    }
  };

  // ─── Export ───────────────────────────────────────────────────────────────
  const handleExport = async (templateId: string) => {
    try {
      const content = await exportTemplate.mutateAsync({ templateId, format: "yaml" });
      const blob = new Blob([content], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${templateId}.yaml`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Template exported");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to export template");
    }
  };

  // ─── Import ───────────────────────────────────────────────────────────────
  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await importTemplate.mutateAsync(file);
      toast.success("Template imported");
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to import template");
    }
    e.target.value = "";
  };

  // ─── Columns ──────────────────────────────────────────────────────────────
  const columns: ColumnDef<Template>[] = [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <div>
          <div className="font-medium">{row.original.name}</div>
          <div className="text-muted-foreground max-w-[300px] truncate text-xs">
            {row.original.description}
          </div>
        </div>
      ),
      size: 280,
    },
    {
      accessorKey: "category",
      header: "Category",
      cell: ({ row }) => {
        const Icon = categoryIcons[row.original.category] ?? FileText;
        return (
          <Badge variant="outline" className="gap-1 text-[10px] capitalize">
            <Icon className="h-3 w-3" />
            {getCategoryDisplayName(row.original.category)}
          </Badge>
        );
      },
      size: 140,
    },
    {
      id: "variables",
      header: "Variables",
      cell: ({ row }) => {
        const vars = row.original.variables;
        const count = Object.keys(vars ?? {}).length;
        return (
          <Badge variant="secondary" className="text-[10px]">
            {count} {count === 1 ? "var" : "vars"}
          </Badge>
        );
      },
      size: 100,
    },
    {
      accessorKey: "is_default",
      header: "Default",
      cell: ({ row }) =>
        row.original.is_default ? (
          <Badge className="bg-green-600 text-[10px]">Default</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">—</span>
        ),
      size: 90,
    },
    {
      accessorKey: "updated_at",
      header: "Updated",
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs">
          {formatRelativeTime(row.original.updated_at)}
        </span>
      ),
      size: 120,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedTemplateId(row.original.id);
              setPreviewVariables({});
              setRenderedContent(null);
              setPreviewOpen(true);
            }}
            title="Preview"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={(e) => {
              e.stopPropagation();
              openEdit(row.original);
            }}
            title="Edit"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={(e) => {
              e.stopPropagation();
              openDuplicate(row.original);
            }}
            title="Duplicate"
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={(e) => {
              e.stopPropagation();
              handleExport(row.original.id);
            }}
            title="Export"
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive h-7 w-7 p-0"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteId(row.original.id);
            }}
            title="Delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
      size: 200,
    },
  ];

  return (
    <div className="container space-y-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Templates</h1>
          <p className="text-muted-foreground">
            Manage reusable templates for specs, plans, protocols, and checklists
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <label aria-label="Import template">
            <Button variant="outline" size="sm" asChild>
              <span>
                <Upload className="mr-2 h-4 w-4" />
                Import
              </span>
            </Button>
            <input
              type="file"
              accept=".yaml,.yml,.json"
              className="hidden"
              onChange={handleImport}
            />
          </label>
          <Button
            size="sm"
            onClick={() => {
              setCreateForm({
                id: "",
                name: "",
                description: "",
                category: "specification",
                content: "",
              });
              setCreateOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            New Template
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]">
        {/* Category Sidebar */}
        <div className="space-y-2">
          <div className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
            Categories
          </div>
          <Button
            variant={selectedCategory === null ? "secondary" : "ghost"}
            size="sm"
            className="w-full justify-start"
            onClick={() => setSelectedCategory(null)}
          >
            All Templates
            <Badge variant="outline" className="ml-auto text-[10px]">
              {categoriesData ? Object.values(categoriesData.counts).reduce((a, b) => a + b, 0) : 0}
            </Badge>
          </Button>
          {categoriesData?.categories.map((cat) => {
            const Icon = categoryIcons[cat] ?? FileText;
            return (
              <Button
                key={cat}
                variant={selectedCategory === cat ? "secondary" : "ghost"}
                size="sm"
                className="w-full justify-start gap-2 capitalize"
                onClick={() => setSelectedCategory(cat)}
              >
                <Icon className="h-4 w-4" />
                {getCategoryDisplayName(cat)}
                <Badge variant="outline" className="ml-auto text-[10px]">
                  {categoriesData.counts[cat] ?? 0}
                </Badge>
              </Button>
            );
          })}
        </div>

        {/* Main Content */}
        <div className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
            <Input
              placeholder="Search templates..."
              className="pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="flex justify-center p-12">
              <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
            </div>
          ) : templates.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <FileText className="text-muted-foreground mb-4 h-12 w-12" />
                <h3 className="text-lg font-medium">No templates found</h3>
                <p className="text-muted-foreground text-sm">
                  Create your first template or adjust your filters.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <DataTable columns={columns} data={templates} enableSearch={false} />
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ─── Create Template Dialog ──────────────────────────────────────── */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Create Template</DialogTitle>
            <DialogDescription>Create a new reusable template.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Template ID</Label>
                <Input
                  value={createForm.id}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, id: e.target.value.replace(/[^a-z0-9-]/g, "") })
                  }
                  placeholder="my-template"
                  className="font-mono text-sm"
                />
                <p className="text-muted-foreground text-[10px]">
                  Lowercase letters, numbers, hyphens only
                </p>
              </div>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={createForm.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    setCreateForm((prev) => ({
                      ...prev,
                      name,
                      id: prev.id || generateTemplateId(name),
                    }));
                  }}
                  placeholder="My Template"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={createForm.description ?? ""}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                placeholder="Brief description of the template"
              />
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={createForm.category}
                onValueChange={(v) =>
                  setCreateForm({ ...createForm, category: v as TemplateCreate["category"] })
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
            <div className="space-y-2">
              <Label>Content</Label>
              <Textarea
                value={createForm.content ?? ""}
                onChange={(e) => setCreateForm({ ...createForm, content: e.target.value })}
                placeholder="Template content with {variable} placeholders..."
                className="min-h-[200px] font-mono text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!createForm.id || !createForm.name || createTemplate.isPending}
            >
              {createTemplate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Edit Template Dialog ────────────────────────────────────────── */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Template</DialogTitle>
            <DialogDescription>Update template content and settings.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={editForm.name ?? ""}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={editForm.description ?? ""}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={editForm.category}
                onValueChange={(v) =>
                  setEditForm({ ...editForm, category: v as TemplateUpdate["category"] })
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
            <div className="space-y-2">
              <Label>Content</Label>
              <Textarea
                value={editForm.content ?? ""}
                onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                className="min-h-[250px] font-mono text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={updateTemplate.isPending}>
              {updateTemplate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Preview / Render Dialog ─────────────────────────────────────── */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-[750px]">
          <DialogHeader>
            <DialogTitle>Preview Template</DialogTitle>
            <DialogDescription>
              Fill in variables to render the template with actual values.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {selectedTemplate && (
              <>
                <div className="flex items-center gap-2 text-sm">
                  <Badge variant="outline">{selectedTemplate.category}</Badge>
                  <span className="font-medium">{selectedTemplate.name}</span>
                </div>

                {Object.keys(selectedTemplateVars).length > 0 && (
                  <div className="space-y-3">
                    <Label className="text-xs font-semibold">Variables</Label>
                    {Object.entries(selectedTemplateVars).map(([key, config]) => (
                      <div key={key} className="grid grid-cols-[1fr_2fr] items-center gap-3">
                        <div>
                          <code className="text-xs font-medium">{key}</code>
                          {config.required && (
                            <span className="text-destructive ml-1 text-xs">*</span>
                          )}
                          {config.description && (
                            <p className="text-muted-foreground text-[10px]">
                              {config.description}
                            </p>
                          )}
                        </div>
                        <Input
                          value={previewVariables[key] ?? config.default?.toString() ?? ""}
                          onChange={(e) =>
                            setPreviewVariables((prev) => ({ ...prev, [key]: e.target.value }))
                          }
                          placeholder={
                            config.type === "string" ? "Enter value..." : `Type: ${config.type}`
                          }
                          className="h-8 text-sm"
                        />
                      </div>
                    ))}
                    <Button
                      size="sm"
                      onClick={handlePreviewRender}
                      disabled={renderTemplate.isPending}
                    >
                      {renderTemplate.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Eye className="mr-2 h-4 w-4" />
                      )}
                      Render Preview
                    </Button>
                  </div>
                )}

                <Separator />

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">
                    {renderedContent ? "Rendered Output" : "Raw Template"}
                  </Label>
                  <ScrollArea className="h-[250px]">
                    <pre className="bg-muted rounded-md p-4 text-xs whitespace-pre-wrap">
                      {renderedContent ?? selectedTemplate.content}
                    </pre>
                  </ScrollArea>
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Duplicate Dialog ────────────────────────────────────────────── */}
      <Dialog open={duplicateOpen} onOpenChange={setDuplicateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duplicate Template</DialogTitle>
            <DialogDescription>Create a copy of this template with a new ID.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>New Template ID</Label>
              <Input
                value={dupId}
                onChange={(e) => setDupId(e.target.value.replace(/[^a-z0-9-]/g, ""))}
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label>New Name</Label>
              <Input value={dupName} onChange={(e) => setDupName(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDuplicateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleDuplicate} disabled={!dupId || duplicateTemplate.isPending}>
              {duplicateTemplate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Duplicate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Delete Confirmation ─────────────────────────────────────────── */}
      <DeleteConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
        itemName={deleteId ?? "this template"}
        itemType="template"
        onConfirm={handleDelete}
        loading={deleteTemplate.isPending}
      />
    </div>
  );
}
