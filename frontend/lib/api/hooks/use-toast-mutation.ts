/**
 * Custom mutation hooks with toast notifications and optimistic updates.
 * These wrap React Query mutations with consistent UI feedback.
 */

import { useMutation, type UseMutationOptions,useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError } from "../client";

interface ToastMutationOptions<TData, TError, TVariables, TContext = unknown> 
  extends UseMutationOptions<TData, TError, TVariables, TContext> {
  successMessage?: string | ((data: TData) => string);
  errorMessage?: string | ((error: TError) => string);
  showToast?: boolean;
}

/**
 * Wrapper around useMutation that adds toast notifications.
 */
export function useToastMutation<TData, TError = ApiError, TVariables = void, TContext = unknown>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: ToastMutationOptions<TData, TError, TVariables, TContext>
) {
  const { 
    successMessage = "Operation successful", 
    errorMessage = "Operation failed",
    showToast = true,
    ...mutationOptions 
  } = options || {};

  return useMutation({
    mutationFn,
    ...mutationOptions,
    onSuccess: (data, variables, context, mutationContext) => {
      if (showToast) {
        const message = typeof successMessage === "function" 
          ? successMessage(data) 
          : successMessage;
        toast.success(message);
      }
      mutationOptions.onSuccess?.(data, variables, context, mutationContext);
    },
    onError: (error, variables, context, mutationContext) => {
      if (showToast) {
        const message = typeof errorMessage === "function" 
          ? errorMessage(error) 
          : errorMessage;
        toast.error(message, {
          description: error instanceof ApiError ? error.message : undefined,
        });
      }
      mutationOptions.onError?.(error, variables, context, mutationContext);
    },
  });
}

interface OptimisticMutationOptions<TData, TError, TVariables, TContext>
  extends ToastMutationOptions<TData, TError, TVariables, TContext> {
  // Query key to invalidate on success
  invalidateKeys?: unknown[][];
  // Optimistic update function
  onOptimisticUpdate?: (variables: TVariables) => TContext;
  // Rollback function
  onRollback?: (context: TContext) => void;
}

/**
 * Wrapper around useMutation that adds optimistic updates.
 */
export function useOptimisticMutation<
  TData, 
  TError = ApiError, 
  TVariables = void,
  TContext = unknown
>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: OptimisticMutationOptions<TData, TError, TVariables, TContext>
) {
  const queryClient = useQueryClient();
  const { 
    invalidateKeys = [],
    onOptimisticUpdate,
    onRollback,
    ...toastOptions 
  } = options || {};

  return useMutation({
    mutationFn,
    onMutate: async (variables) => {
      // Cancel any outgoing refetches
      if (invalidateKeys.length > 0) {
        await Promise.all(
          invalidateKeys.map(key => queryClient.cancelQueries({ queryKey: key }))
        );
      }

      // Apply optimistic update
      if (onOptimisticUpdate) {
        return onOptimisticUpdate(variables);
      }
    },
    onError: (error, variables, context, mutationContext) => {
      // Rollback on error
      if (context !== undefined && onRollback) {
        onRollback(context as TContext);
      }
      
      // Show toast
      if (toastOptions.showToast !== false) {
        const { errorMessage = "Operation failed" } = toastOptions;
        const message = typeof errorMessage === "function" 
          ? errorMessage(error as TError) 
          : errorMessage;
        toast.error(message, {
          description: error instanceof ApiError ? error.message : undefined,
        });
      }
      
      toastOptions.onError?.(error as TError, variables, context as TContext | undefined, mutationContext);
    },
    onSuccess: (data, variables, context, mutationContext) => {
      // Show success toast
      if (toastOptions.showToast !== false) {
        const { successMessage = "Operation successful" } = toastOptions;
        const message = typeof successMessage === "function" 
          ? successMessage(data) 
          : successMessage;
        toast.success(message);
      }
      
      toastOptions.onSuccess?.(data, variables, context as TContext, mutationContext);
    },
    onSettled: (data, error, variables, context) => {
      // Invalidate queries
      invalidateKeys.forEach(key => {
        queryClient.invalidateQueries({ queryKey: key });
      });
    },
  });
}

// =============================================================================
// Pre-configured mutation hooks for common operations
// =============================================================================

/**
 * Delete mutation with confirmation toast.
 */
export function useDeleteMutation<TVariables = { id: number }>(
  deleteFn: (variables: TVariables) => Promise<void>,
  options?: {
    itemName?: string;
    invalidateKeys?: unknown[][];
    onSuccess?: () => void;
  }
) {
  const { itemName = "Item", invalidateKeys = [], onSuccess } = options || {};
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteFn,
    onMutate: () => {
      toast.loading(`Deleting ${itemName.toLowerCase()}...`, { id: "delete" });
    },
    onSuccess: () => {
      toast.success(`${itemName} deleted successfully`, { id: "delete" });
      invalidateKeys.forEach(key => {
        queryClient.invalidateQueries({ queryKey: key });
      });
      onSuccess?.();
    },
    onError: (error) => {
      toast.error(`Failed to delete ${itemName.toLowerCase()}`, { 
        id: "delete",
        description: error instanceof ApiError ? error.message : undefined,
      });
    },
  });
}

/**
 * Create mutation with loading toast.
 */
export function useCreateMutation<TData, TVariables>(
  createFn: (variables: TVariables) => Promise<TData>,
  options?: {
    itemName?: string;
    invalidateKeys?: unknown[][];
    onSuccess?: (data: TData) => void;
  }
) {
  const { itemName = "Item", invalidateKeys = [], onSuccess } = options || {};
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createFn,
    onMutate: () => {
      toast.loading(`Creating ${itemName.toLowerCase()}...`, { id: "create" });
    },
    onSuccess: (data) => {
      toast.success(`${itemName} created successfully`, { id: "create" });
      invalidateKeys.forEach(key => {
        queryClient.invalidateQueries({ queryKey: key });
      });
      onSuccess?.(data);
    },
    onError: (error) => {
      toast.error(`Failed to create ${itemName.toLowerCase()}`, { 
        id: "create",
        description: error instanceof ApiError ? error.message : undefined,
      });
    },
  });
}

/**
 * Update mutation with loading toast.
 */
export function useUpdateMutation<TData, TVariables>(
  updateFn: (variables: TVariables) => Promise<TData>,
  options?: {
    itemName?: string;
    invalidateKeys?: unknown[][];
    onSuccess?: (data: TData) => void;
  }
) {
  const { itemName = "Item", invalidateKeys = [], onSuccess } = options || {};
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateFn,
    onMutate: () => {
      toast.loading(`Updating ${itemName.toLowerCase()}...`, { id: "update" });
    },
    onSuccess: (data) => {
      toast.success(`${itemName} updated successfully`, { id: "update" });
      invalidateKeys.forEach(key => {
        queryClient.invalidateQueries({ queryKey: key });
      });
      onSuccess?.(data);
    },
    onError: (error) => {
      toast.error(`Failed to update ${itemName.toLowerCase()}`, { 
        id: "update",
        description: error instanceof ApiError ? error.message : undefined,
      });
    },
  });
}
