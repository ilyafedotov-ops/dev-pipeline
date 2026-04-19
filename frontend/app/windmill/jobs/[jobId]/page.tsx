"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, FileText, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWindmillJob, useWindmillJobLogs } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  Running: "default",
  Success: "secondary",
  Failed: "destructive",
  Cancelled: "outline",
  Done: "secondary",
  Queued: "outline",
};

export default function JobDetailPage() {
  const params = useParams();
  const jobIdParam = params?.jobId;
  const jobId = Array.isArray(jobIdParam) ? jobIdParam[0] : jobIdParam;

  const { data: job, isLoading: jobLoading, error: jobError } = useWindmillJob(jobId ?? "");
  const { data: logs, isLoading: logsLoading } = useWindmillJobLogs(jobId ?? "");

  if (jobLoading) return <LoadingState message="Loading job..." />;
  if (jobError) {
    const message = jobError instanceof Error ? jobError.message : "Job not found";
    return (
      <div className="container py-8">
        <EmptyState title="Job not found" description={message} />
      </div>
    );
  }

  const logsContent = typeof logs === "string"
    ? logs
    : logs?.content
      ? logs.content
      : logs
        ? JSON.stringify(logs, null, 2)
        : null;

  return (
    <div className="container space-y-8 py-8">
      <div className="mb-6">
        <Link
          href="/windmill/jobs"
          className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Jobs
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold">
              <span className="font-mono">{jobId?.slice(0, 16)}...</span>
              {job?.status && (
                <Badge variant={statusVariant[job.status] ?? "outline"}>
                  {job.status}
                </Badge>
              )}
            </h1>
            <p className="text-muted-foreground mt-1 font-mono text-sm">
              {job?.script_path ?? "Unknown script"}
            </p>
          </div>
        </div>
      </div>

      {/* Job Info Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
          </CardHeader>
          <CardContent>
            {job?.status ? (
              <Badge variant={statusVariant[job.status] ?? "outline"}>{job.status}</Badge>
            ) : (
              <span className="text-muted-foreground">-</span>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Created</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium text-sm">{formatDateTime(job?.created_at)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Duration</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium text-sm">
              {job?.started_at
                ? formatDuration(job.started_at, job.finished_at ?? undefined as unknown as string)
                : "-"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Kind</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-medium text-sm capitalize">{job?.job_kind ?? "-"}</p>
          </CardContent>
        </Card>
      </div>

      {/* Timestamps */}
      <div className="grid gap-4 text-sm md:grid-cols-3">
        <div>
          <span className="text-muted-foreground">Created:</span>{" "}
          {formatDateTime(job?.created_at)}
        </div>
        <div>
          <span className="text-muted-foreground">Started:</span>{" "}
          {formatDateTime(job?.started_at)}
        </div>
        <div>
          <span className="text-muted-foreground">Finished:</span>{" "}
          {formatDateTime(job?.finished_at)}
        </div>
      </div>

      {/* Details Tabs */}
      <Tabs defaultValue="result" className="space-y-4">
        <TabsList>
          <TabsTrigger value="result">Result</TabsTrigger>
          {job?.error && <TabsTrigger value="error">Error</TabsTrigger>}
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="result">
          <Card>
            <CardHeader>
              <CardTitle>Result</CardTitle>
            </CardHeader>
            <CardContent>
              {job?.result ? (
                <CodeBlock
                  code={
                    typeof job.result === "string"
                      ? job.result
                      : JSON.stringify(job.result, null, 2)
                  }
                  maxHeight="500px"
                />
              ) : (
                <EmptyState title="No result" description="This job has no result data." />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {job?.error && (
          <TabsContent value="error">
            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">Error</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-destructive bg-destructive/10 rounded-lg p-4 text-sm whitespace-pre-wrap">
                  {job.error}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <CardTitle>Execution Logs</CardTitle>
            </CardHeader>
            <CardContent>
              {logsLoading ? (
                <LoadingState message="Loading logs..." />
              ) : logsContent ? (
                <CodeBlock
                  code={typeof logsContent === "string" ? logsContent : JSON.stringify(logsContent, null, 2)}
                  maxHeight="500px"
                />
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No logs available"
                  description="Logs have not been recorded for this job."
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
