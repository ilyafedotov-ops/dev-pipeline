"use client";

import { useState } from "react";
import { Activity, Clock, type LucideIcon, Save, Shield } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import {
  useChangePassword,
  useProfile,
  useUpdateProfile,
  useUserProfile,
} from "@/lib/api";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ProfilePage() {
  const { data: profileData, isLoading: profileLoading } = useProfile();
  const { data: userData, isLoading: userLoading } = useUserProfile();
  const { user: authUser } = useAuth();

  const isLoading = profileLoading || userLoading;

  if (isLoading) {
    return <LoadingState message="Loading profile..." />;
  }

  const user = profileData;

  const iconMap: Record<string, LucideIcon> = {
    activity: Activity,
  };

  return (
    <div className="container max-w-5xl py-8">
      <div className="mb-8 flex items-start gap-6">
        <Avatar className="h-24 w-24">
          <AvatarFallback className="bg-primary text-primary-foreground text-2xl">
            {(authUser?.name || user?.name || "DU").slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <h1 className="mb-2 text-3xl font-bold">
            {authUser?.name || user?.name}
          </h1>
          <p className="text-muted-foreground mb-4">
            {authUser?.email || user?.email}
          </p>
          <div className="flex gap-2">
            <Badge variant="secondary">
              <Shield className="mr-1 h-3 w-3" />
              {authUser?.role || user?.role}
            </Badge>
            {user?.member_since && (
              <Badge variant="outline">
                <Clock className="mr-1 h-3 w-3" />
                Member since {user.member_since}
              </Badge>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile">Profile Settings</TabsTrigger>
          <TabsTrigger value="password">Password</TabsTrigger>
          <TabsTrigger value="activity">Activity Log</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <ProfileForm
            defaultName={authUser?.name || userData?.name || user?.name || ""}
            defaultEmail={
              authUser?.email || userData?.email || user?.email || ""
            }
          />
        </TabsContent>

        <TabsContent value="password" className="space-y-6">
          <PasswordChangeForm />
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>
                Your recent actions across projects.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {user?.activity?.map((item) => {
                  const Icon = iconMap[item.icon] || Activity;
                  return (
                    <div
                      key={item.id}
                      className="flex items-start gap-4 border-b pb-4 last:border-0 last:pb-0"
                    >
                      <div className="bg-muted mt-1 flex h-8 w-8 items-center justify-center rounded-full">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">{item.action}</p>
                        <p className="text-muted-foreground text-sm">
                          {item.target}
                        </p>
                      </div>
                      <span className="text-muted-foreground text-xs">
                        {item.time}
                      </span>
                    </div>
                  );
                })}
                {!user?.activity?.length && (
                  <p className="text-muted-foreground text-sm">
                    No recent activity.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---------- Profile Edit Form ---------- */

function ProfileForm({
  defaultName,
  defaultEmail,
}: {
  defaultName: string;
  defaultEmail: string;
}) {
  const [name, setName] = useState(defaultName);
  const [email, setEmail] = useState(defaultEmail);

  const updateProfile = useUpdateProfile();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile.mutate(
      { name, email },
      {
        onSuccess: () => {
          // Refresh the page data after successful update
          // Query invalidation is handled by the hook
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Personal Information</CardTitle>
        <CardDescription>Update your personal details.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your full name"
                disabled={updateProfile.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                disabled={updateProfile.isPending}
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={updateProfile.isPending}>
              {updateProfile.isPending ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/* ---------- Password Change Form ---------- */

function PasswordChangeForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const changePassword = useChangePassword();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (newPassword.length < 6) {
      setValidationError("New password must be at least 6 characters.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setValidationError("New passwords do not match.");
      return;
    }

    changePassword.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
          setValidationError(null);
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change Password</CardTitle>
        <CardDescription>
          Update your password to keep your account secure.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">Current Password</Label>
            <Input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              required
              disabled={changePassword.isPending}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                required
                disabled={changePassword.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm New Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                required
                disabled={changePassword.isPending}
              />
            </div>
          </div>

          {validationError && (
            <p className="text-sm text-destructive">{validationError}</p>
          )}

          <div className="flex justify-end">
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Changing...
                </>
              ) : (
                "Change Password"
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
