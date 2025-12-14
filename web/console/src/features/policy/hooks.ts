import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { PolicyPack } from '@/api/types';

export function usePolicyPacks() {
  return useQuery({
    queryKey: ['policy', 'packs'],
    queryFn: () => apiClient.fetch<PolicyPack[]>('/policy_packs'),
  });
}

export function useCreatePolicyPack() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { key: string; version: string; name: string; description?: string; pack: Record<string, unknown> }) =>
      apiClient.fetch<PolicyPack>('/policy_packs', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policy', 'packs'] });
    },
  });
}
