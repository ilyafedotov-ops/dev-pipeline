"use client"

import { useState } from "react"
import { useSpecifications } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { FileText, Search, Plus, Filter, ListTodo, Target } from "lucide-react"
import Link from "next/link"

export default function SpecificationsPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const { data: specifications, isLoading } = useSpecifications()

  const statusColors: Record<string, string> = {
    draft: "bg-gray-500",
    "in-progress": "bg-blue-500",
    completed: "bg-green-500",
    failed: "bg-red-500",
  }

  if (isLoading) {
    return <LoadingState message="Loading specifications..." />
  }

  const filteredSpecs = (specifications || []).filter(
    (spec) =>
      spec.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      spec.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
      spec.project_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (!specifications || specifications.length === 0) {
    return (
      <div className="flex h-full flex-col gap-6 p-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Specifications</h1>
          <p className="text-sm text-muted-foreground">Feature specifications and implementation plans</p>
        </div>
        <EmptyState
          icon={FileText}
          title="No specifications found"
          description="Create specifications using SpecKit to see them here."
          action={
            <Button asChild>
              <Link href="/projects">
                <Plus className="mr-2 h-4 w-4" />
                Go to Projects
              </Link>
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Specifications</h1>
        <p className="text-sm text-muted-foreground">Feature specifications and implementation plans</p>
      </div>

      <div className="flex items-center gap-4 rounded-lg border bg-card px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-blue-400" />
          <span className="font-medium">Total Specs:</span>
          <span className="text-muted-foreground">{specifications.length}</span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <ListTodo className="h-4 w-4 text-green-400" />
          <span className="font-medium">With Tasks:</span>
          <span className="text-muted-foreground">{specifications.filter((s) => s.tasks_generated).length}</span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-purple-400" />
          <span className="font-medium">In Sprints:</span>
          <span className="text-muted-foreground">{specifications.filter((s) => s.sprint_id).length}</span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="font-medium">Total Story Points:</span>
          <span className="text-muted-foreground">{specifications.reduce((sum, s) => sum + s.story_points, 0)}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search specifications..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button variant="outline" size="sm">
          <Filter className="mr-2 h-4 w-4" />
          Filter
        </Button>
        <Button size="sm" asChild>
          <Link href="/projects">
            <Plus className="mr-2 h-4 w-4" />
            New Spec
          </Link>
        </Button>
      </div>

      <div className="grid gap-4">
        {filteredSpecs.map((spec) => (
          <Card key={spec.id} className="transition-colors hover:bg-muted/50">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <FileText className="mt-0.5 h-5 w-5 text-blue-500" />
                  <div>
                    <CardTitle className="text-base">{spec.title}</CardTitle>
                    <CardDescription className="mt-1 font-mono text-xs">{spec.path}</CardDescription>
                  </div>
                </div>
                <Badge variant="secondary" className={`${statusColors[spec.status] || "bg-gray-500"} text-white`}>
                  {spec.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Project: {spec.project_name}</span>
                  <span>•</span>
                  <span>Created: {spec.created_at || "-"}</span>
                  {spec.sprint_name && (
                    <>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <Target className="h-3 w-3 text-purple-400" />
                        <span className="text-purple-400">{spec.sprint_name}</span>
                      </div>
                    </>
                  )}
                  {spec.linked_tasks > 0 && (
                    <>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <ListTodo className="h-3 w-3 text-green-400" />
                        <span className="text-green-400">
                          {spec.completed_tasks}/{spec.linked_tasks} tasks
                        </span>
                      </div>
                    </>
                  )}
                  {spec.story_points > 0 && (
                    <>
                      <span>•</span>
                      <span className="font-medium">{spec.story_points} pts</span>
                    </>
                  )}
                  {spec.protocol_id && (
                    <>
                      <span>•</span>
                      <span>Protocol: #{spec.protocol_id}</span>
                    </>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/specifications/${spec.id}`}>View</Link>
                  </Button>
                  {spec.protocol_id && (
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/protocols/${spec.protocol_id}`}>Protocol</Link>
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
