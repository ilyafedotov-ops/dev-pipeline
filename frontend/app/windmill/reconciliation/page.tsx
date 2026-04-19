"use client";

import { useState } from "react";
import Link from "next/link";

import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, RefreshCw, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useReconciliationStatus, useRunReconciliation } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

export default function ReconciliationPage() {
  const [dryRun, setDryRun] = useState(false);
  const [background, setBackground] = useState(false);

  const { data: status, isLoading, refetch } = useReconciliationStatus();
  const reconcile = useRunReconciliation();

  return (
    <div className="container space-y-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/windmill"
            className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
          >
            ← Back to Windmill
          </Link>
          <h1 className="text-2xl font-bold">Reconciliation</h1>
          <p className="text-muted-foreground">
            Track and trigger protocol/step reconciliation jobs
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <LoadingState message="Loading reconciliation status..." />
      ) : (
        <>
          {/* Status Overview */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Last Run</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-sm font-medium">
                  {status?.last_run ? formatRelativeTime(status.last_run) : "Never"}
                </span>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total Reconciled</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-2xl font-bold">
                  {status?.total_reconciled ?? 0}
                </span>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Last Status</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-sm font-medium capitalize">
                  {status?.last_status ?? "-"}
                </span>
              </CardContent>
            </Card>
          </div>

          {/* Trigger Reconciliation */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Trigger Reconciliation
              </CardTitle>
              <CardDescription>
                Start a new reconciliation run for all pending protocols and steps
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="dry-run"
                    checked={dryRun}
                    onCheckedChange={(v) => setDryRun(v === true)}
                  />
                  <label htmlFor="dry-run" className="text-sm cursor-pointer">
                    Dry run (preview only)
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="background"
                    checked={background}
                    onCheckedChange={(v) => setBackground(v === true)}
                  />
                  <label htmlFor="background" className="text-sm cursor-pointer">
                    Run in background
                  </label>
                </div>
                <Button
                  onClick={() =>
                    reconcile.mutate({
                      dry_run: dryRun,
                      background,
                    })
                  }
                  disabled={reconcile.isPending}
                >
                  {reconcile.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Trigger Reconciliation
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Last Report */}
          {status?.last_report && (
            <Card>
              <CardHeader>
                <CardTitle>Last Reconciliation Report</CardTitle>
                <CardDescription>
                  {status.last_run ? formatDateTime(status.last_run) : ""}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CodeBlock
                  code={
                    typeof status.last_report === "string"
                      ? status.last_report
                      : JSON.stringify(status.last_report, null, 2)
                  }
                  maxHeight="400px"
                />
              </CardContent>
            </Card>
          )}

          {/* Protocol / Step Drill-down */}
          {(status?.protocols || status?.steps) && (
            <div className="grid gap-4 md:grid-cols-2">
              {status.protocols && (
                <Card>
                  <CardHeader>
                    <CardTitle>Protocol Runs</CardTitle>
                    <CardDescription>Reconciled protocol runs</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-muted max-h-64 overflow-auto rounded-lg p-3 font-mono text-xs whitespace-pre-wrap">
                      {typeof status.protocols === "string"
                        ? status.protocols
                        : JSON.stringify(status.protocols, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}
              {status.steps && (
                <Card>
                  <CardHeader>
                    <CardTitle>Step Runs</CardTitle>
                    <CardDescription>Reconciled step runs</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-muted max-h-64 overflow-auto rounded-lg p-3 font-mono text-xs whitespace-pre-wrap">
                      {typeof status.steps === "string"
                        ? status.steps
                        : JSON.stringify(status.steps, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {!status?.last_report && !status?.protocols && !status?.steps && (
            <EmptyState
              icon={ShieldCheck}
              title="No reconciliation data"
              description="No reconciliation reports yet. Trigger a reconciliation to see results."
            />
          )}
        </>
      )}
    </div>
  );
}
