"use client";
import { use } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ArrowLeft,
  ClipboardCheck,
  FileSearch,
  FileText,
  ListTodo,
  Play,
  Target,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SpecificationViewer } from "@/components/features/specification-viewer";
import { useSpecification, useSpecificationContent } from "@/lib/api";
import {
  getProjectExecutionPath,
  getSpecificationDetailPath,
  getSpecificationReviewPath,
  type SpecificationDetailTab,
} from "@/lib/project-routes";

const SPECIFICATION_DETAIL_TABS: readonly SpecificationDetailTab[] = [
  "overview",
  "tasks",
  "spec_file",
  "plan_file",
  "tasks_file",
  "checklist",
  "analysis",
  "protocol",
];

export default function SpecificationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const id = Number.parseInt(resolvedParams.id);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: spec, isLoading } = useSpecification(id);
  const { data: specContent, isLoading: contentLoading } = useSpecificationContent(id);

  if (isLoading) {
    return <LoadingState message="Loading specification..." />;
  }

  if (!spec) {
    return (
      <div className="flex h-full flex-col gap-6 p-6">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/specifications">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>
        <EmptyState
          icon={FileText}
          title="Specification not found"
          description="The specification you are looking for does not exist."
          action={
            <Button asChild>
              <Link href="/specifications">View All Specifications</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    draft: "bg-gray-500",
    "in-progress": "bg-blue-500",
    completed: "bg-green-500",
    failed: "bg-red-500",
  };
  const hasChecklist = Boolean(spec.checklist_path);
  const hasAnalysis = Boolean(spec.analysis_path);
  const hasExecution = Boolean(spec.protocol_id || spec.implement_path);
  const reviewReady = Boolean(spec.has_tasks && hasChecklist && hasAnalysis);
  const searchTab = searchParams.get("tab");
  const currentTab = SPECIFICATION_DETAIL_TABS.includes(searchTab as SpecificationDetailTab)
    ? (searchTab as SpecificationDetailTab)
    : "overview";

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/specifications">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <FileText className="h-5 w-5 text-blue-500" />
          <div>
            <h1 className="text-2xl font-semibold">{spec.title}</h1>
            <p className="text-muted-foreground text-sm">{spec.path}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant="secondary"
            className={`${statusColors[spec.status] || "bg-gray-500"} text-white`}
          >
            {spec.status}
          </Badge>
          <Button size="sm" variant={currentTab === "analysis" ? "secondary" : "default"} asChild>
            <Link href={getSpecificationReviewPath(spec.id)}>
              <FileSearch className="mr-2 h-4 w-4" />
              Review Implementation
            </Link>
          </Button>
          {spec.protocol_id && (
            <Button size="sm" variant="outline" asChild>
              <Link href={`/protocols/${spec.protocol_id}`}>
                <Play className="mr-2 h-4 w-4" />
                View Protocol
              </Link>
            </Button>
          )}
          {spec.sprint_id && (
            <Button size="sm" variant="outline" asChild>
              <Link href={getProjectExecutionPath(spec.project_id, spec.sprint_id)}>
                <Target className="mr-2 h-4 w-4" />
                Open Execution
              </Link>
            </Button>
          )}
        </div>
      </div>

      <div className="bg-card flex items-center gap-4 rounded-lg border px-4 py-3 text-sm">
        {spec.sprint_name && (
          <>
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-400" />
              <span className="font-medium">Execution:</span>
              <span className="text-purple-400">{spec.sprint_name}</span>
            </div>
            <div className="bg-border h-4 w-px" />
          </>
        )}
        <div className="flex items-center gap-2">
          <ListTodo className="h-4 w-4 text-blue-400" />
          <span className="font-medium">Tasks:</span>
          <span className="text-muted-foreground">
            {spec.completed_tasks}/{spec.linked_tasks}
          </span>
        </div>
        <div className="bg-border h-4 w-px" />
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-green-400" />
          <span className="font-medium">Story Points:</span>
          <span className="text-muted-foreground">{spec.story_points}</span>
        </div>
        <div className="bg-border h-4 w-px" />
        <div className="flex items-center gap-2">
          <span className="font-medium">Project:</span>
          <span className="text-muted-foreground">{spec.project_name}</span>
        </div>
      </div>

      <Tabs
        value={currentTab}
        onValueChange={(nextTab) =>
          router.replace(getSpecificationDetailPath(spec.id, nextTab as SpecificationDetailTab))
        }
        className="flex-1"
      >
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tasks">Tasks ({spec.linked_tasks})</TabsTrigger>
          <TabsTrigger value="spec_file">Spec File</TabsTrigger>
          <TabsTrigger value="plan_file">Plan File</TabsTrigger>
          <TabsTrigger value="tasks_file">Tasks File</TabsTrigger>
          <TabsTrigger value="checklist">Checklist</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
          <TabsTrigger value="protocol">Protocol</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Specification Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-muted-foreground text-sm">Path</p>
                  <p className="font-mono text-sm">{spec.path}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Status</p>
                  <Badge className={`${statusColors[spec.status] || "bg-gray-500"} text-white`}>
                    {spec.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Tasks Generated</p>
                  <p className="text-sm">{spec.tasks_generated ? "Yes" : "No"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Story Points</p>
                  <p className="text-sm">{spec.story_points}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Review Status</p>
                  <p className="text-sm">{reviewReady ? "Review Ready" : "Missing review artifacts"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Execution Status</p>
                  <p className="text-sm">{hasExecution ? "Execution bootstrapped" : "No protocol linked"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Checklist</p>
                  <p className="text-sm">{hasChecklist ? "Generated" : "Not generated"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Analysis</p>
                  <p className="text-sm">{hasAnalysis ? "Generated" : "Not generated"}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Generated Tasks</CardTitle>
              <CardDescription>
                {spec.linked_tasks} task(s) • {spec.story_points} total story points
              </CardDescription>
            </CardHeader>
            <CardContent>
              {spec.linked_tasks === 0 ? (
                <div className="text-muted-foreground py-4 text-sm">
                  No tasks have been generated for this specification yet.
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm">
                    {spec.completed_tasks} of {spec.linked_tasks} tasks completed
                  </p>
                  <div className="bg-muted h-2 rounded-full">
                    <div
                      className="h-2 rounded-full bg-green-500 transition-all"
                      style={{
                        width: `${spec.linked_tasks > 0 ? (spec.completed_tasks / spec.linked_tasks) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  {spec.sprint_id && (
                    <div className="mt-4">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={getProjectExecutionPath(spec.project_id, spec.sprint_id)}>
                          View in Execution
                        </Link>
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Integrated SpecificationViewer component for spec content tabs */}
        <TabsContent value="spec_file" className="space-y-4">
          <SpecificationViewer specId={id} />
        </TabsContent>

        <TabsContent value="plan_file" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>plan.md</CardTitle>
              <CardDescription>Rendered as plain Markdown text</CardDescription>
            </CardHeader>
            <CardContent>
              {contentLoading ? (
                <LoadingState message="Loading plan content..." />
              ) : specContent?.plan_content ? (
                <CodeBlock code={specContent.plan_content} language="markdown" maxHeight="600px" />
              ) : (
                <div className="text-muted-foreground text-sm">No plan content available yet.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tasks_file" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>tasks.md</CardTitle>
              <CardDescription>Rendered as plain Markdown text</CardDescription>
            </CardHeader>
            <CardContent>
              {contentLoading ? (
                <LoadingState message="Loading tasks content..." />
              ) : specContent?.tasks_content ? (
                <CodeBlock code={specContent.tasks_content} language="markdown" maxHeight="600px" />
              ) : (
                <div className="text-muted-foreground text-sm">No tasks content available yet.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="checklist" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-emerald-500" />
                Checklist
              </CardTitle>
              <CardDescription>SpecKit checklist for this specification</CardDescription>
            </CardHeader>
            <CardContent>
              {specContent?.checklist_content ? (
                <CodeBlock
                  code={specContent.checklist_content}
                  language="markdown"
                  maxHeight="600px"
                />
              ) : (
                <div className="text-muted-foreground text-sm">
                  No checklist generated yet. Run the checklist action from the SpecKit workspace.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analysis tab — shows ambiguities detected by LLM Clarifier and implementation review */}
        <TabsContent value="analysis" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSearch className="h-4 w-4 text-sky-500" />
                Analysis
              </CardTitle>
              <CardDescription>Implementation review summary for this specification</CardDescription>
            </CardHeader>
            <CardContent>
              {contentLoading ? (
                <LoadingState message="Loading analysis content..." />
              ) : specContent?.analysis_content ? (
                <CodeBlock code={specContent.analysis_content} language="markdown" maxHeight="600px" />
              ) : (
                <div className="text-muted-foreground text-sm">
                  No analysis generated yet. Run the analysis action from the SpecKit workspace.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="protocol" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Protocol Execution</CardTitle>
            </CardHeader>
            <CardContent>
              {spec.protocol_id ? (
                <div className="space-y-2">
                  <p className="text-sm">Protocol ID: #{spec.protocol_id}</p>
                  <p className="text-muted-foreground text-sm">
                    {reviewReady ? "Implementation review is ready." : "Complete checklist and analysis for review readiness."}
                  </p>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/protocols/${spec.protocol_id}`}>View Protocol Details</Link>
                  </Button>
                  {spec.sprint_id && (
                    <Button variant="outline" size="sm" asChild>
                      <Link href={getProjectExecutionPath(spec.project_id, spec.sprint_id)}>
                        Open Execution Sprint
                      </Link>
                    </Button>
                  )}
                </div>
              ) : (
                <div className="text-muted-foreground text-sm">No protocol created yet</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
