"use client";

/**
 * Convenience re-exports for settings page hooks.
 * The primary implementations live in lib/api/hooks/use-profile.ts
 */
export {
  useUserProfile,
  useUpdateProfile,
  useChangePassword,
  type UserAccount,
  type UpdateProfilePayload,
  type ChangePasswordPayload,
} from "../api/hooks/use-profile";
