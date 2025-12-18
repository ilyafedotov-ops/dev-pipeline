"use client"

import { useProfile } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { LoadingState } from "@/components/ui/loading-state"
import { Shield, Clock, CheckCircle2, GitBranch, PlayCircle, Activity } from "lucide-react"

export default function ProfilePage() {
  const { data: user, isLoading } = useProfile()

  if (isLoading) {
    return <LoadingState message="Loading profile..." />
  }

  const iconMap: Record<string, any> = {
    activity: Activity,
  }

  return (
    <div className="container max-w-5xl py-8">
      <div className="flex items-start gap-6 mb-8">
        <Avatar className="h-24 w-24">
          <AvatarFallback className="bg-primary text-primary-foreground text-2xl">
            {user?.name.slice(0, 2).toUpperCase() || "DU"}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <h1 className="text-3xl font-bold mb-2">{user?.name}</h1>
          <p className="text-muted-foreground mb-4">{user?.email}</p>
          <div className="flex gap-2">
            <Badge variant="secondary">
              <Shield className="h-3 w-3 mr-1" />
              {user?.role}
            </Badge>
            <Badge variant="outline">
              <Clock className="h-3 w-3 mr-1" />
              Member since {user?.member_since}
            </Badge>
          </div>
        </div>
        <Button>Edit Profile</Button>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile">Profile Settings</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="activity">Activity Log</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Personal Information</CardTitle>
              <CardDescription>Update your personal details.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">Full Name</Label>
                  <Input id="firstName" defaultValue={user?.name} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" defaultValue={user?.email} />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Your recent actions across projects.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {user?.activity.map((item) => {
                  const Icon = iconMap[item.icon] || Activity
                  return (
                    <div key={item.id} className="flex items-start gap-4 pb-4 border-b last:border-0 last:pb-0">
                      <div className="mt-1 h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">{item.action}</p>
                        <p className="text-sm text-muted-foreground">{item.target}</p>
                      </div>
                      <span className="text-xs text-muted-foreground">{item.time}</span>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        {/* Other tabs omitted for brevity */}
      </Tabs>
    </div>
  )
}
