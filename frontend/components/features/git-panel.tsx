"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { GitBranch, GitCommit, GitPullRequest, ExternalLink, CheckCircle2, XCircle, Clock } from "lucide-react"

interface GitPanelProps {
  className?: string
}

interface Branch {
  name: string
  commit: string
  isProtected: boolean
  lastUpdated: string
}

interface PullRequest {
  id: string
  title: string
  branch: string
  status: "open" | "merged" | "closed"
  checks: "passing" | "failing" | "pending"
  url: string
}

const mockBranches: Branch[] = [
  { name: "main", commit: "abc123f", isProtected: true, lastUpdated: "2 hours ago" },
  { name: "feature/user-auth", commit: "def456a", isProtected: false, lastUpdated: "5 hours ago" },
  { name: "bugfix/login-error", commit: "ghi789b", isProtected: false, lastUpdated: "1 day ago" },
]

const mockPRs: PullRequest[] = [
  {
    id: "1",
    title: "Add user authentication system",
    branch: "feature/user-auth",
    status: "open",
    checks: "passing",
    url: "#",
  },
  {
    id: "2",
    title: "Fix login error handling",
    branch: "bugfix/login-error",
    status: "open",
    checks: "pending",
    url: "#",
  },
]

export function GitPanel({ className }: GitPanelProps) {
  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Branches
          </CardTitle>
          <CardDescription>Active branches in this repository</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {mockBranches.map((branch) => (
              <div key={branch.name} className="flex items-center justify-between rounded-lg border p-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{branch.name}</p>
                    {branch.isProtected && (
                      <Badge variant="secondary" className="text-xs">
                        Protected
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    <GitCommit className="inline h-3 w-3 mr-1" />
                    {branch.commit} • {branch.lastUpdated}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitPullRequest className="h-5 w-5" />
            Pull Requests
          </CardTitle>
          <CardDescription>Open pull requests and their CI status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {mockPRs.map((pr) => (
              <div key={pr.id} className="flex items-start justify-between rounded-lg border p-3">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{pr.title}</p>
                    <Badge variant={pr.status === "open" ? "default" : "secondary"} className="text-xs">
                      {pr.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{pr.branch}</p>
                  <div className="flex items-center gap-2 mt-2">
                    {pr.checks === "passing" && (
                      <div className="flex items-center gap-1 text-xs text-green-600">
                        <CheckCircle2 className="h-3 w-3" />
                        All checks passing
                      </div>
                    )}
                    {pr.checks === "failing" && (
                      <div className="flex items-center gap-1 text-xs text-red-600">
                        <XCircle className="h-3 w-3" />
                        Some checks failing
                      </div>
                    )}
                    {pr.checks === "pending" && (
                      <div className="flex items-center gap-1 text-xs text-yellow-600">
                        <Clock className="h-3 w-3" />
                        Checks pending
                      </div>
                    )}
                  </div>
                </div>
                <Button variant="ghost" size="sm" asChild>
                  <a href={pr.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
