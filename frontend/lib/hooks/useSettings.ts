"use client";

/**
 * Convenience re-exports for settings page hooks.
 * The primary implementations live in lib/api/hooks/use-profile.ts
 */
export {
  type ChangePasswordPayload,
  type UpdateProfilePayload,
  useChangePassword,
  type UserAccount,
  useUpdateProfile,
  useUserProfile,
} from "../api/hooks/use-profile";
