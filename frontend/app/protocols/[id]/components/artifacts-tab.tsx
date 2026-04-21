"use client";

import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { Code2, Download, Eye, FileBox, FileText, Image } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useProtocolArtifacts } from "@/lib/api";
import { apiClient } from "@/lib/api/client";
import type { ArtifactContent, ProtocolArtifact } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";

interface ArtifactsTabProps {
  protocolId: number;
}

function artifactIcon(kind: string) {
  if (kind === "code" || kind === "diff") return Code2;
  if (kind === "image" || kind === "screenshot") return Image;
  return FileText;
}

function formatBytes(bytes: number | null | undefined) {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getArtifactEndpoints(artifact: ProtocolArtifact): {
  content: string | null;
  download: string | null;
} {
  const artifactId = encodeURIComponent(artifact.id);
  if (artifact.step_run_id != null) {
    const base = `/steps/${artifact.step_run_id}/artifacts/${artifactId}`;
    return { content: `${base}/content`, download: `${base}/download` };
  }
  if (artifact.run_id) {
    const base = `/runs/${encodeURIComponent(artifact.run_id)}/artifacts/${artifactId}`;
    return { content: `${base}/content`, download: `${base}/download` };
  }
  return { content: null, download: null };
}

function languageForKind(kind: string, name: string): string {
  if (kind === "diff") return "diff";
  if (kind === "code") {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext && ext !== name.toLowerCase()) return ext;
    return "text";
  }
  if (name.endsWith(".json")) return "json";
  if (name.endsWith(".md")) return "markdown";
  if (name.endsWith(".yaml") || name.endsWith(".yml")) return "yaml";
  return "text";
}

function ArtifactContentDialog({
  artifact,
  open,
  onOpenChange,
}: {
  artifact: ProtocolArtifact | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const endpoints = artifact ? getArtifactEndpoints(artifact) : { content: null, download: null };
  const contentPath = endpoints.content;

  const { data, isLoading, error } = useQuery<ArtifactContent>({
    queryKey: ["protocolArtifactContent", artifact?.id, contentPath],
    queryFn: () => apiClient.get<ArtifactContent>(contentPath as string),
    enabled: open && !!contentPath,
  });

  const isImage = artifact && (artifact.kind === "image" || artifact.kind === "screenshot");
  const downloadUrl = endpoints.download
    ? `${apiClient.getConfig().baseUrl}${endpoints.download}`
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileBox className="h-5 w-5" />
            <span className="truncate">{artifact?.name ?? "Artifact"}</span>
            {artifact?.kind && (
              <Badge variant="outline" className="text-[10px]">
                {artifact.kind}
              </Badge>
            )}
          </DialogTitle>
          {artifact?.path && (
            <DialogDescription className="font-mono text-xs break-all">
              {artifact.path}
            </DialogDescription>
          )}
        </DialogHeader>

        {!contentPath ? (
          <EmptyState
            title="Cannot open artifact"
            description="This artifact has no associated step or run id."
          />
        ) : isImage && downloadUrl ? (
          <img
            src={downloadUrl}
            alt={artifact?.name ?? "artifact"}
            className="max-h-[70vh] w-full rounded-md border object-contain"
          />
        ) : isLoading ? (
          <LoadingState message="Loading artifact..." />
        ) : error ? (
          <EmptyState
            title="Failed to load artifact"
            description={error instanceof Error ? error.message : "Unknown error"}
          />
        ) : data ? (
          <div className="space-y-2">
            {data.truncated && (
              <p className="text-muted-foreground text-xs italic">
                Content truncated — download the file for the full contents.
              </p>
            )}
            <CodeBlock
              code={data.content ?? ""}
              language={languageForKind(artifact?.kind ?? "", artifact?.name ?? "")}
              maxHeight="60vh"
            />
          </div>
        ) : null}

        {downloadUrl && (
          <div className="flex justify-end">
            <Button asChild variant="outline" size="sm">
              <a href={downloadUrl} download={artifact?.name ?? undefined}>
                <Download className="mr-2 h-4 w-4" />
                Download
              </a>
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ArtifactsTab({ protocolId }: ArtifactsTabProps) {
  const { data: artifacts, isLoading } = useProtocolArtifacts(protocolId);
  const [openArtifact, setOpenArtifact] = useState<ProtocolArtifact | null>(null);

  if (isLoading) return <LoadingState message="Loading artifacts..." />;
  if (!artifacts || artifacts.length === 0) {
    return (
      <EmptyState
        icon={FileBox}
        title="No artifacts"
        description="Protocol artifacts will appear here after steps produce output."
      />
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileBox className="h-5 w-5" />
            Protocol Artifacts
          </CardTitle>
          <CardDescription>{artifacts.length} artifact(s) across all steps</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {artifacts.map((artifact) => {
              const Icon = artifactIcon(artifact.kind);
              const endpoints = getArtifactEndpoints(artifact);
              const canOpen = !!endpoints.content;
              const downloadUrl = endpoints.download
                ? `${apiClient.getConfig().baseUrl}${endpoints.download}`
                : null;
              return (
                <div key={artifact.id} className="flex items-center gap-3 rounded-lg border p-3">
                  <Icon className="text-muted-foreground h-5 w-5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{artifact.name}</span>
                      <Badge variant="outline" className="shrink-0 text-[10px]">
                        {artifact.kind}
                      </Badge>
                    </div>
                    <div className="text-muted-foreground mt-1 flex items-center gap-3 text-xs">
                      <span className="truncate">{artifact.path}</span>
                      <span>{formatBytes(artifact.bytes)}</span>
                      <span>{formatRelativeTime(artifact.created_at)}</span>
                    </div>
                  </div>
                  {artifact.step_run_id && (
                    <Badge variant="secondary" className="shrink-0 text-[10px]">
                      Step #{artifact.step_run_id}
                    </Badge>
                  )}
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setOpenArtifact(artifact)}
                      disabled={!canOpen}
                      title={canOpen ? "View artifact" : "Artifact has no step or run context"}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    {downloadUrl && (
                      <Button asChild variant="ghost" size="sm" title="Download">
                        <a href={downloadUrl} download={artifact.name}>
                          <Download className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <ArtifactContentDialog
        artifact={openArtifact}
        open={!!openArtifact}
        onOpenChange={(open) => {
          if (!open) setOpenArtifact(null);
        }}
      />
    </div>
  );
}
