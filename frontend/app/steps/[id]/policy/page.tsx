"use client"

import { useStepPolicyFindings } from "@/lib/api"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { ArrowLeft, AlertTriangle, Info } from "lucide-react"
import Link from "next/link"
import type { PolicyFinding } from "@/lib/api/types"

export default function StepPolicyPage({ params }: { params: { id: string } }) {
  const { id } = params
  const stepId = Number.parseInt(id)
  const { data: findings, isLoading } = useStepPolicyFindings(stepId)

  if (isLoading) {
    return <LoadingState />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/steps/${id}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Step
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Step Policy Findings</h1>
          <p className="text-sm text-muted-foreground">Step #{stepId}</p>
        </div>
      </div>

      {findings && findings.length > 0 ? (
        <div className="space-y-3">
          {findings.map((finding: PolicyFinding, idx: number) => (
            <Card key={idx} className="p-4">
              <div className="flex items-start gap-3">
                {finding.severity === "error" ? (
                  <AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
                ) : (
                  <Info className="h-5 w-5 text-yellow-500 mt-0.5" />
                )}
                <div className="flex-1">
                  <div className="font-medium">{finding.code}</div>
                  <div className="text-sm text-muted-foreground mt-1">{finding.message}</div>
                  {finding.suggested_fix && (
                    <div className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                      Suggestion: {finding.suggested_fix}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-12">
          <EmptyState title="No policy findings" description="This step has no policy violations." />
        </Card>
      )}
    </div>
  )
}
