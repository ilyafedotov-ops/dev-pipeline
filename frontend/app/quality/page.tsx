"use client"

import { useQualityDashboard } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { CheckCircle2, AlertTriangle, XCircle, Shield, FileCheck, RefreshCw } from "lucide-react"
import Link from "next/link"

export default function QualityPage() {
  const { data: dashboard, isLoading, refetch } = useQualityDashboard()

  const statusIcons: Record<string, React.ReactNode> = {
    passed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    warning: <AlertTriangle className="h-4 w-4 text-amber-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
  }

  if (isLoading) {
    return <LoadingState message="Loading quality dashboard..." />
  }

  if (!dashboard) {
    return (
      <div className="flex h-full flex-col gap-6 p-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Quality Assurance</h1>
          <p className="text-sm text-muted-foreground">Constitutional gates and quality metrics</p>
        </div>
        <EmptyState
          icon={Shield}
          title="No quality data available"
          description="Run protocols to see quality metrics here."
        />
      </div>
    )
  }

  const { overview, recent_findings, constitutional_gates } = dashboard

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Quality Assurance</h1>
          <p className="text-sm text-muted-foreground">Constitutional gates and quality metrics</p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="bg-muted/50 border rounded-lg p-4">
        <div className="flex items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-blue-500/10 flex items-center justify-center">
              <Shield className="h-4 w-4 text-blue-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Total Protocols</div>
              <div className="text-2xl font-bold">{overview.total_protocols}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-green-500/10 flex items-center justify-center">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Passed</div>
              <div className="text-2xl font-bold">{overview.passed}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-amber-500/10 flex items-center justify-center">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Warnings</div>
              <div className="text-2xl font-bold">{overview.warnings}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-red-500/10 flex items-center justify-center">
              <XCircle className="h-4 w-4 text-red-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Failed</div>
              <div className="text-2xl font-bold">{overview.failed}</div>
            </div>
          </div>

          <div className="h-12 w-px bg-border" />

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-purple-500/10 flex items-center justify-center">
              <FileCheck className="h-4 w-4 text-purple-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Avg Score</div>
              <div className="text-2xl font-bold">{overview.average_score}%</div>
            </div>
          </div>
        </div>
      </div>

      <Tabs defaultValue="gates" className="flex-1">
        <TabsList>
          <TabsTrigger value="gates">Constitutional Gates</TabsTrigger>
          <TabsTrigger value="findings">Recent Findings ({recent_findings.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="gates" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {constitutional_gates.map((gate) => (
              <Card key={gate.article}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Article {gate.article}</CardTitle>
                    {statusIcons[gate.status]}
                  </div>
                  <CardDescription>{gate.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Checks</span>
                    <Badge variant={gate.status === "passed" ? "default" : gate.status === "failed" ? "destructive" : "secondary"}>
                      {gate.checks}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="findings" className="space-y-4">
          {recent_findings.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="No findings"
              description="No quality issues detected. Great job!"
            />
          ) : (
            <div className="space-y-4">
              {recent_findings.map((finding) => (
                <Card key={finding.id}>
                  <CardContent className="pt-4">
                    <div className="flex items-start gap-4">
                      {finding.severity === "error" ? (
                        <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
                      ) : (
                        <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5" />
                      )}
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <p className="font-medium">{finding.message}</p>
                          <Badge variant={finding.severity === "error" ? "destructive" : "secondary"}>
                            {finding.severity}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>{finding.project_name}</span>
                          <span>•</span>
                          <span>Article {finding.article}: {finding.article_name}</span>
                          <span>•</span>
                          <span>{finding.timestamp}</span>
                        </div>
                      </div>
                      {finding.protocol_id > 0 && (
                        <Button variant="ghost" size="sm" asChild>
                          <Link href={`/protocols/${finding.protocol_id}`}>View</Link>
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
