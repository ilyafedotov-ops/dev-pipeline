"use client";

import { type FormEvent, use, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, Copy, Edit } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusPill } from "@/components/ui/status-pill";
import { Textarea } from "@/components/ui/textarea";
import { useClonePolicyPack, usePolicyPack, usePolicyPackVersions } from "@/lib/api";
import type { PolicyPack } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export default function PolicyPackDetailPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = use(params);
  const query = useSearchParams();
  const selectedVersion = query.get("version") ?? undefined;
  const router = useRouter();
  const { data: pack, isLoading, error } = usePolicyPack(key, selectedVersion);
  const { data: versions, isLoading: versionsLoading } = usePolicyPackVersions(key);

  if (isLoading) return <LoadingState message="Loading policy pack..." />;
  if (error) {
    const message = error instanceof Error ? error.message : "Failed to load policy pack";
    return (
      <div className="container py-8">
        <EmptyState title="Error loading policy pack" description={message} />
      </div>
    );
  }

  if (!pack) {
    return (
      <div className="container py-8">
        <EmptyState title="Policy pack not found" description={`No policy pack exists for key ${key}.`} />
      </div>
    );
  }

  return (
    <div className="container py-8">
      <div className="mb-6">
        <Link
          href="/policy-packs"
          className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Policy Packs
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-2xl font-bold">{pack.key}</h1>
              <StatusPill status={pack.is_builtin ? "completed" : "pending"} size="sm" />
            </div>
            <p className="text-muted-foreground mt-1">{pack.name}</p>
          </div>
          <div className="flex items-center gap-2">
            <ClonePolicyPackDialog sourcePack={pack} />
            {pack.editable && (
              <Button variant="outline" asChild>
                <Link href={`/policy-packs/${key}/edit${selectedVersion ? `?version=${selectedVersion}` : ""}`}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </Link>
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mb-6 grid gap-6 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Version</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-mono text-lg">{pack.version}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Source</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{pack.is_builtin ? "Built-in preset" : "Custom pack"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
          </CardHeader>
          <CardContent>
            <StatusPill status={pack.status === "active" ? "completed" : "pending"} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Created</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{formatDateTime(pack.created_at)}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {pack.description && (
            <Card>
              <CardHeader>
                <CardTitle>Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">{pack.description}</p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Pack Configuration</CardTitle>
              <CardDescription>JSON policy definition</CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock code={pack.pack} title={`${pack.key}@${pack.version}`} maxHeight="600px" />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Versions</CardTitle>
              <CardDescription>
                {versionsLoading ? "Loading history..." : `${versions?.length ?? 0} version(s)`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {(versions ?? []).map((item) => {
                const href = `/policy-packs/${item.key}${item.version ? `?version=${item.version}` : ""}`;
                const active = item.version === pack.version;
                return (
                  <button
                    key={`${item.key}:${item.version}`}
                    type="button"
                    onClick={() => router.push(href)}
                    className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm ${active ? "border-primary bg-primary/5" : "hover:border-primary/50"}`}
                  >
                    <span className="font-mono">{item.version}</span>
                    <span className="text-muted-foreground">{item.status}</span>
                  </button>
                );
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Editing</CardTitle>
              <CardDescription>
                {pack.editable
                  ? "This pack can be edited in place."
                  : "Built-in packs are immutable. Clone to make changes."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {pack.editable ? (
                <Button variant="outline" className="w-full" asChild>
                  <Link href={`/policy-packs/${key}/edit${selectedVersion ? `?version=${selectedVersion}` : ""}`}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit This Pack
                  </Link>
                </Button>
              ) : (
                <ClonePolicyPackDialog sourcePack={pack} triggerClassName="w-full" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function ClonePolicyPackDialog({
  sourcePack,
  triggerClassName,
}: {
  sourcePack: PolicyPack;
  triggerClassName?: string;
}) {
  const clonePack = useClonePolicyPack();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState(() => ({
    key: `${sourcePack.key}-custom`,
    version: "1.0",
    name: `${sourcePack.name} Clone`,
    description: sourcePack.description ?? "",
  }));

  const resetForm = () => {
    setFormData({
      key: `${sourcePack.key}-custom`,
      version: "1.0",
      name: `${sourcePack.name} Clone`,
      description: sourcePack.description ?? "",
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const created = await clonePack.mutateAsync({
        sourceKey: sourcePack.key,
        sourceVersion: sourcePack.version,
        data: {
          key: formData.key,
          version: formData.version,
          name: formData.name,
          description: formData.description || undefined,
        },
      });
      toast.success("Policy pack cloned");
      setOpen(false);
      resetForm();
      router.push(`/policy-packs/${created.key}?version=${created.version}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to clone policy pack");
    }
  };

  const triggerLabel = sourcePack.is_builtin ? "Clone Preset" : "Clone Pack";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={sourcePack.is_builtin ? "default" : "outline"} className={triggerClassName}>
          <Copy className="mr-2 h-4 w-4" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clone Policy Pack</DialogTitle>
          <DialogDescription>
            Create a new custom pack from {sourcePack.key}@{sourcePack.version}.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="clone-key">Key</Label>
              <Input
                id="clone-key"
                value={formData.key}
                onChange={(e) => setFormData((current) => ({ ...current, key: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clone-version">Version</Label>
              <Input
                id="clone-version"
                value={formData.version}
                onChange={(e) => setFormData((current) => ({ ...current, version: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clone-name">Name</Label>
              <Input
                id="clone-name"
                value={formData.name}
                onChange={(e) => setFormData((current) => ({ ...current, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clone-description">Description</Label>
              <Textarea
                id="clone-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((current) => ({ ...current, description: e.target.value }))
                }
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={clonePack.isPending}>
              {clonePack.isPending ? "Cloning..." : "Clone"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
