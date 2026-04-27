import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";

export interface Features {
  windmill_enabled: boolean;
  task_cycle_enabled: boolean;
}

export function useFeatures() {
  return useQuery<Features>({
    queryKey: queryKeys.features.list(),
    queryFn: () => apiClient.get<Features>("/features"),
    staleTime: 5 * 60 * 1000, // 5 min cache — features don't change often
    retry: false,
  });
}
