"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"

// Types for Profile
export interface ActivityItem {
    id: string
    action: string
    target: string
    time: string
    icon: string
}

export interface UserProfile {
    id: string
    name: string
    email: string
    role: string
    member_since: string
    activity: ActivityItem[]
}

// Get Profile
export function useProfile() {
    return useQuery({
        queryKey: queryKeys.profile.me(),
        queryFn: () => apiClient.get<UserProfile>("/profile"),
    })
}
