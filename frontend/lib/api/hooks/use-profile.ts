"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../client";
import { queryKeys } from "../query-keys";

// Types for Profile
export interface ActivityItem {
  id: string;
  action: string;
  target: string;
  time: string;
  icon: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  member_since: string;
  activity: ActivityItem[];
}

// Types for User Account (from /users/me)
export interface UserAccount {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member" | "viewer";
  avatar?: string;
  company?: string;
  created_at?: string;
}

export interface UpdateProfilePayload {
  name?: string;
  email?: string;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

// Get Profile (activity feed)
export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile.me(),
    queryFn: () => apiClient.get<UserProfile>("/profile"),
  });
}

// Get User Account (from /users/me)
export function useUserProfile() {
  return useQuery({
    queryKey: queryKeys.users.me(),
    queryFn: () => apiClient.get<UserAccount>("/users/me"),
  });
}

// Update User Profile (PUT /users/me)
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateProfilePayload) =>
      apiClient.put<UserAccount>("/users/me", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.me() });
      toast.success("Profile updated successfully");
    },
    onError: (error) => {
      toast.error("Failed to update profile", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    },
  });
}

// Change Password
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordPayload) =>
      apiClient.post("/users/me/password", data),
    onSuccess: () => {
      toast.success("Password changed successfully");
    },
    onError: (error) => {
      toast.error("Failed to change password", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    },
  });
}
