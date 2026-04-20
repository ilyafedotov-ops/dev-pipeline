"use client";

import { use } from "react";
import Link from "next/link";

import { AlertTriangle, ArrowLeft, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useStepPolicyFindings } from "@/lib/api";
import type { PolicyFinding } from "@/lib/api/types";

export default function StepPolicyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const stepId = Number.parseInt(id, 10);
  const { data: findings, isLoading } = useStepPolicyFindings(stepId);

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/steps/${id}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Step
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Step Policy Findings</h1>
          <p className="text-muted-foreground text-sm">Step #{stepId}</p>
        </div>
      </div>

      {findings && findings.length > 0 ? (
        <div className="space-y-3">
          {findings.map((finding: PolicyFinding, idx: number) => (
            <Card key={idx} className="p-4">
              <div className="flex items-start gap-3">
                {finding.severity === "error" ? (
                  <AlertTriangle className="text-destructive mt-0.5 h-5 w-5" />
                ) : (
                  <Info className="mt-0.5 h-5 w-5 text-yellow-500" />
                )}
                <div className="flex-1">
                  <div className="font-medium">{finding.code}</div>
                  <div className="text-muted-foreground mt-1 text-sm">{finding.message}</div>
                  {finding.suggested_fix && (
                    <div className="text-muted-foreground bg-muted/50 mt-2 rounded p-2 text-sm">
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
          <EmptyState
            title="No policy findings"
            description="This step has no policy violations."
          />
        </Card>
      )}
    </div>
  );
}
