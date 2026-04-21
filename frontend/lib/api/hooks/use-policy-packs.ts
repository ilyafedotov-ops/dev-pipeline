"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";
import type { PolicyPack, PolicyPackCloneRequest, PolicyPackContent } from "../types";

// List Policy Packs
export function usePolicyPacks(filters?: { key?: string; status?: string }) {
  return useQuery({
    queryKey: queryKeys.policyPacks.list(filters),
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters?.key) params.set("key", filters.key);
      if (filters?.status) params.set("status", filters.status);
      const query = params.toString();
      return apiClient.get<PolicyPack[]>(`/policy_packs${query ? `?${query}` : ""}`);
    },
  });
}

export function usePolicyPack(key: string | undefined, version?: string) {
  return useQuery({
    queryKey: queryKeys.policyPacks.detail(key ?? "", version),
    queryFn: () =>
      apiClient.get<PolicyPack>(
        version ? `/policy_packs/${key}/${version}` : `/policy_packs/${key}`
      ),
    enabled: Boolean(key),
  });
}

export function usePolicyPackVersions(key: string | undefined) {
  return useQuery({
    queryKey: queryKeys.policyPacks.versions(key ?? ""),
    queryFn: () => apiClient.get<PolicyPack[]>(`/policy_packs?key=${encodeURIComponent(key ?? "")}`),
    enabled: Boolean(key),
  });
}

// Create/Update Policy Pack
export function useCreatePolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      key: string;
      version: string;
      name: string;
      description?: string;
      status?: PolicyPack["status"];
      pack: PolicyPackContent;
    }) => apiClient.post<PolicyPack>("/policy_packs", data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.policyPacks.all,
      });
    },
  });
}

export function useClonePolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sourceKey,
      sourceVersion,
      data,
    }: {
      sourceKey: string;
      sourceVersion: string;
      data: PolicyPackCloneRequest;
    }) =>
      apiClient.post<PolicyPack>(`/policy_packs/${sourceKey}/${sourceVersion}/clone`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.policyPacks.all,
      });
    },
  });
}
