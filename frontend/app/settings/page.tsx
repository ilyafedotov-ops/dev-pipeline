"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";

import {
  Bell,
  CheckCircle2,
  Copy,
  Globe,
  Key,
  Link,
  Save,
  SettingsIcon,
  Shield,
  User,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient, useHealth } from "@/lib/api";
import {
  useChangePassword,
  useUpdateProfile,
  useUserProfile,
} from "@/lib/api/hooks/use-profile";

export default function SettingsPage() {
  const [apiBase, setApiBase] = useState(() => apiClient.getConfig().baseUrl);
  const [token, setToken] = useState(() => apiClient.getConfig().token || "");
  const [webhookUrl, setWebhookUrl] = useState("");
  const { data: health, isError, refetch } = useHealth();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    setWebhookUrl(`${window.location.origin}/api/v1/webhooks/events`);
  }, []);

  const handleSave = () => {
    apiClient.configure({
      baseUrl: apiBase,
      token: token || undefined,
    });
    toast.success("Settings saved successfully");
    refetch();
  };

  return (
    <div className="container max-w-5xl py-8">
      <div className="mb-8">
        <h1 className="mb-2 text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your console configuration and preferences.</p>
      </div>

      <Tabs defaultValue="general" className="space-y-6">
        <TabsList>
          <TabsTrigger value="general">
            <SettingsIcon className="mr-2 h-4 w-4" />
            General
          </TabsTrigger>
          <TabsTrigger value="account">
            <User className="mr-2 h-4 w-4" />
            Account
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Link className="mr-2 h-4 w-4" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="mr-2 h-4 w-4" />
            Notifications
          </TabsTrigger>
        </TabsList>

        {/* ─── Tab 1: General ─── */}
        <TabsContent value="general" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>API Configuration</CardTitle>
              <CardDescription>
                Configure the connection to your DevGodzilla API server.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="apiBase">API Base URL</Label>
                <Input
                  id="apiBase"
                  placeholder="http://localhost:8011"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                />
                <p className="text-muted-foreground text-xs">
                  The base URL of your DevGodzilla API server
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="token">API Token (optional)</Label>
                <Input
                  id="token"
                  type="password"
                  placeholder="Enter your API token"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
                <p className="text-muted-foreground text-xs">Bearer token for API authentication</p>
              </div>
              <Button onClick={handleSave}>Save Configuration</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Connection Status</CardTitle>
              <CardDescription>Current connection status to the API server.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3 rounded-lg border p-4">
                {health?.status === "ok" ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <div className="flex-1">
                      <p className="font-medium text-green-500">Connected</p>
                      <p className="text-muted-foreground text-sm">
                        API server is responding normally
                      </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => refetch()}>
                      Test Connection
                    </Button>
                  </>
                ) : (
                  <>
                    <XCircle className="text-destructive h-5 w-5" />
                    <div className="flex-1">
                      <p className="text-destructive font-medium">Disconnected</p>
                      <p className="text-muted-foreground text-sm">
                        {isError ? "Unable to reach API server" : "Checking connection..."}
                      </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => refetch()}>
                      Retry
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Display Preferences</CardTitle>
              <CardDescription>Customize how the console displays information.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Dark Mode</p>
                  <p className="text-muted-foreground text-sm">Always use dark theme</p>
                </div>
                <Switch
                  checked={theme === "dark"}
                  onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
                />
              </div>
              <Separator />
              <div className="space-y-2">
                <Label>Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Select language" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Español</SelectItem>
                    <SelectItem value="fr">Français</SelectItem>
                    <SelectItem value="de">Deutsch</SelectItem>
                    <SelectItem value="ja">日本語</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Auto-refresh Data</p>
                  <p className="text-muted-foreground text-sm">
                    Automatically refresh active protocol data
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab 2: Account ─── */}
        <TabsContent value="account" className="space-y-6">
          <AccountSettings />
        </TabsContent>

        {/* ─── Tab 3: Integrations ─── */}
        <TabsContent value="integrations" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>GitHub Integration</CardTitle>
              <CardDescription>Connect your GitHub account for repository access.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">GitHub Connection</p>
                  <p className="text-muted-foreground text-sm">
                    Connect to GitHub for pull request and branch management
                  </p>
                </div>
                <Button variant="outline">Connect GitHub</Button>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Status</p>
                  <p className="text-muted-foreground text-sm">Not connected</p>
                </div>
                <XCircle className="h-5 w-5 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Windmill Integration</CardTitle>
              <CardDescription>Windmill workflow engine connection status.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Windmill Server</p>
                  <p className="text-muted-foreground text-sm">
                    Connection to the Windmill automation engine
                  </p>
                </div>
                <Button variant="outline" onClick={() => refetch()}>
                  Test Connection
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>API Access</CardTitle>
              <CardDescription>Manage your API token and webhook configuration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>API Token</Label>
                <div className="flex gap-2">
                  <Input
                    type="password"
                    value={apiClient.getConfig().token || "No token configured"}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      const t = apiClient.getConfig().token;
                      if (t) {
                        navigator.clipboard.writeText(t);
                        toast.success("API token copied to clipboard");
                      } else {
                        toast.error("No API token configured");
                      }
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <Separator />
              <div className="space-y-2">
                <Label>Webhook URL</Label>
                <div className="flex gap-2">
                  <Input
                    readOnly
                    value={webhookUrl}
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    disabled={!webhookUrl}
                    onClick={() => {
                      if (!webhookUrl) return;
                      navigator.clipboard.writeText(webhookUrl);
                      toast.success("Webhook URL copied to clipboard");
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-muted-foreground text-xs">
                  Use this URL to receive webhook events from external services
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab 4: Notifications ─── */}
        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Notification Channels</CardTitle>
              <CardDescription>Choose how you want to receive notifications.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Email Notifications</p>
                  <p className="text-muted-foreground text-sm">
                    Receive notifications via email
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Webhook Notifications</p>
                  <p className="text-muted-foreground text-sm">
                    Send notifications to an external webhook endpoint
                  </p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Event Notifications</CardTitle>
              <CardDescription>Choose which events trigger notifications.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Protocol Completion</p>
                  <p className="text-muted-foreground text-sm">
                    Notify when protocols finish executing
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Policy Violations</p>
                  <p className="text-muted-foreground text-sm">Alert on policy check failures</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Run Failures</p>
                  <p className="text-muted-foreground text-sm">Notify when runs encounter errors</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">System Alerts</p>
                  <p className="text-muted-foreground text-sm">Important system notifications</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Work Item Updates</p>
                  <p className="text-muted-foreground text-sm">
                    Notify on work item status changes
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Agent Activity</p>
                  <p className="text-muted-foreground text-sm">
                    Notify when agents start or complete tasks
                  </p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Account Settings Sub-component ───

function AccountSettings() {
  const { data: user, isLoading } = useUserProfile();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [initialized, setInitialized] = useState(false);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Fallback to demo user when API returns null (demo mode without real auth)
  const displayUser = user || {
    id: "demo",
    email: "demo@devgodzilla.dev",
    name: "Demo User",
    role: "admin" as const,
    created_at: new Date().toISOString(),
  };

  // Sync user data to local state once loaded
  if (displayUser && !initialized) {
    setDisplayName(displayUser.name || "");
    setEmail(displayUser.email || "");
    setInitialized(true);
  }

  const handleSaveProfile = () => {
    updateProfile.mutate({ name: displayName, email });
  };

  const handleChangePassword = () => {
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    changePassword.mutate(
      { current_password: oldPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setOldPassword("");
          setNewPassword("");
          setConfirmPassword("");
        },
      }
    );
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Profile Information</CardTitle>
          <CardDescription>
            Manage your display name, email, and other account details.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading profile...</p>
          ) : displayUser ? (
            <div className="rounded-lg border p-4 space-y-2">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">User ID</span>
                  <p className="font-mono">{displayUser.id}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Role</span>
                  <p className="capitalize">{displayUser.role}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Member Since</span>
                  <p>{displayUser.created_at ? new Date(displayUser.created_at).toLocaleDateString() : "N/A"}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Company</span>
                  <p>{displayUser.company || "N/A"}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              Unable to load profile. Ensure you are logged in.
            </p>
          )}

          <Separator />

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                placeholder="Your display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="accountEmail">Email</Label>
              <Input
                id="accountEmail"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <Button
              onClick={handleSaveProfile}
              disabled={updateProfile.isPending}
            >
              <Save className="mr-2 h-4 w-4" />
              {updateProfile.isPending ? "Saving..." : "Save Profile"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>Update your account password.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="oldPassword">Current Password</Label>
            <Input
              id="oldPassword"
              type="password"
              placeholder="Enter current password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="newPassword">New Password</Label>
            <Input
              id="newPassword"
              type="password"
              placeholder="Enter new password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm New Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              placeholder="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <Button
            onClick={handleChangePassword}
            disabled={changePassword.isPending || !oldPassword || !newPassword}
          >
            <Key className="mr-2 h-4 w-4" />
            {changePassword.isPending ? "Changing..." : "Change Password"}
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
