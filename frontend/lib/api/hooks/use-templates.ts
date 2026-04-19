"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";

// =============================================================================
// Types
// =============================================================================

/**
 * Template variable configuration
 */
export interface TemplateVariableConfig {
  type: string;
  required: boolean;
  default?: unknown;
  enum?: string[];
  description?: string;
}

/**
 * Template response from the API
 */
export interface Template {
  id: string;
  name: string;
  description: string;
  category: "specification" | "plan" | "protocol" | "checklist";
  content: string;
  variables: Record<string, TemplateVariableConfig>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  is_default: boolean;
}

/**
 * Template creation request
 */
export interface TemplateCreate {
  id: string;
  name: string;
  description?: string;
  category?: "specification" | "plan" | "protocol" | "checklist";
  content?: string;
  variables?: Record<string, TemplateVariableConfig>;
  metadata?: Record<string, unknown>;
}

/**
 * Template update request
 */
export interface TemplateUpdate {
  name?: string;
  description?: string;
  category?: "specification" | "plan" | "protocol" | "checklist";
  content?: string;
  variables?: Record<string, TemplateVariableConfig>;
  metadata?: Record<string, unknown>;
}

/**
 * Template list response
 */
export interface TemplateListResponse {
  items: Template[];
  total: number;
  categories: string[];
}

/**
 * Rendered template response
 */
export interface TemplateRenderResponse {
  content: string;
  template_id: string;
}

/**
 * Categories response
 */
export interface CategoriesResponse {
  categories: string[];
  counts: Record<string, number>;
}

// =============================================================================
// Query Keys
// =============================================================================

export const templateKeys = {
  all: ["templates"] as const,
  lists: () => [...templateKeys.all, "list"] as const,
  list: (filters: { category?: string; search?: string }) =>
    [...templateKeys.lists(), filters] as const,
  details: () => [...templateKeys.all, "detail"] as const,
  detail: (id: string) => [...templateKeys.details(), id] as const,
  categories: () => [...templateKeys.all, "categories"] as const,
};

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch list of templates with optional filtering
 */
export function useTemplates(options?: { category?: string; search?: string }) {
  const params = new URLSearchParams();
  if (options?.category) {
    params.set("category", options.category);
  }
  if (options?.search) {
    params.set("search", options.search);
  }

  const queryString = params.toString();
  const path = queryString ? `/templates?${queryString}` : "/templates";

  return useQuery({
    queryKey: templateKeys.list({
      category: options?.category,
      search: options?.search,
    }),
    queryFn: () => apiClient.get<TemplateListResponse>(path),
  });
}

/**
 * Fetch a single template by ID
 */
export function useTemplate(templateId: string) {
  return useQuery({
    queryKey: templateKeys.detail(templateId),
    queryFn: () => apiClient.get<Template>(`/templates/${templateId}`),
    enabled: !!templateId,
  });
}

/**
 * Fetch template categories with counts
 */
export function useTemplateCategories() {
  return useQuery({
    queryKey: templateKeys.categories(),
    queryFn: () => apiClient.get<CategoriesResponse>("/templates/categories"),
  });
}

/**
 * Create a new template
 */
export function useCreateTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (template: TemplateCreate) => apiClient.post<Template>("/templates", template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
      queryClient.invalidateQueries({ queryKey: templateKeys.categories() });
    },
  });
}

/**
 * Update an existing template
 */
export function useUpdateTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: TemplateUpdate }) =>
      apiClient.patch<Template>(`/templates/${id}`, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: templateKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}

/**
 * Delete a template
 */
export function useDeleteTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/templates/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
      queryClient.invalidateQueries({ queryKey: templateKeys.categories() });
    },
  });
}

/**
 * Duplicate a template
 */
export function useDuplicateTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      templateId,
      newId,
      newName,
    }: {
      templateId: string;
      newId: string;
      newName?: string;
    }) => {
      const params = new URLSearchParams();
      params.set("new_id", newId);
      if (newName) {
        params.set("new_name", newName);
      }
      return apiClient.post<Template>(`/templates/${templateId}/duplicate?${params.toString()}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}

/**
 * Render a template with variables
 */
export function useRenderTemplate() {
  return useMutation({
    mutationFn: ({
      templateId,
      variables,
    }: {
      templateId: string;
      variables: Record<string, unknown>;
    }) =>
      apiClient.post<TemplateRenderResponse>(`/templates/${templateId}/render`, {
        variables,
      }),
  });
}

/**
 * Export a template as YAML or JSON
 */
export function useExportTemplate() {
  return useMutation({
    mutationFn: async ({
      templateId,
      format = "yaml",
    }: {
      templateId: string;
      format?: "yaml" | "json";
    }) => {
      const response = await fetch(`/api/v1/templates/${templateId}/export?format=${format}`);
      if (!response.ok) {
        throw new Error("Failed to export template");
      }
      return response.text();
    },
  });
}

/**
 * Import a template from file
 */
export function useImportTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/v1/templates/import", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Failed to import template");
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
      queryClient.invalidateQueries({ queryKey: templateKeys.categories() });
    },
  });
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get category display name
 */
export function getCategoryDisplayName(category: string): string {
  const names: Record<string, string> = {
    specification: "Specifications",
    plan: "Plans",
    protocol: "Protocols",
    checklist: "Checklists",
  };
  return names[category] || category;
}

/**
 * Get category icon name (for lucide-react)
 */
export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    specification: "FileText",
    plan: "ListTodo",
    protocol: "Workflow",
    checklist: "CheckSquare",
  };
  return icons[category] || "File";
}

/**
 * Extract variable names from template content
 */
export function extractVariables(content: string): string[] {
  const regex = /\{(\w+)\}/g;
  const variables = new Set<string>();
  let match;

  while ((match = regex.exec(content)) !== null) {
    variables.add(match[1]);
  }

  return Array.from(variables);
}

/**
 * Validate template ID format
 */
export function validateTemplateId(id: string): { valid: boolean; error?: string } {
  if (!id) {
    return { valid: false, error: "ID is required" };
  }

  if (id.length > 100) {
    return { valid: false, error: "ID must be 100 characters or less" };
  }

  if (!/^[a-z0-9-]+$/.test(id)) {
    return {
      valid: false,
      error: "ID must contain only lowercase letters, numbers, and hyphens",
    };
  }

  return { valid: true };
}

/**
 * Generate a template ID from name
 */
export function generateTemplateId(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}
