"use client";

import { type FormEvent, use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, Copy, Save } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { useClonePolicyPack, useCreatePolicyPack, usePolicyPack } from "@/lib/api";

export default function EditPolicyPackPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params);
  const searchParams = useSearchParams();
  const version = searchParams.get("version") ?? undefined;
  const router = useRouter();
  const { data: pack, isLoading, error } = usePolicyPack(key, version);
  const upsertPack = useCreatePolicyPack();

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    version: "",
    pack: "",
  });

  useEffect(() => {
    if (!pack) return;
    setFormData({
      name: pack.name ?? "",
      description: pack.description ?? "",
      version: pack.version ?? "",
      pack: JSON.stringify(pack.pack ?? {}, null, 2),
    });
  }, [pack]);

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

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const packJson = JSON.parse(formData.pack);
      await upsertPack.mutateAsync({
        key,
        version: formData.version,
        name: formData.name,
        description: formData.description || undefined,
        status: pack.status,
        pack: packJson,
      });
      toast.success("Policy pack updated successfully");
      router.push(`/policy-packs/${key}?version=${formData.version}`);
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON in pack configuration");
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to update policy pack");
      }
    }
  };

  if (!pack.editable) {
    return (
      <div className="container py-8">
        <div className="mb-6">
          <Link
            href={`/policy-packs/${key}${version ? `?version=${version}` : ""}`}
            className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Pack
          </Link>
          <h1 className="text-2xl font-bold">Built-in Policy Pack</h1>
          <p className="text-muted-foreground font-mono">
            {pack.key}@{pack.version}
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card>
            <CardHeader>
              <CardTitle>Read-only preset</CardTitle>
              <CardDescription>
                Built-in packs are immutable. Clone this preset into a custom key to make changes.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock code={pack.pack} title={`${pack.key}@${pack.version}`} maxHeight="600px" />
            </CardContent>
          </Card>
          <ClonePolicyPackDialog sourceKey={pack.key} sourceVersion={pack.version} sourceName={pack.name} sourceDescription={pack.description ?? ""} />
        </div>
      </div>
    );
  }

  return (
    <div className="container py-8">
      <div className="mb-6">
        <Link
          href={`/policy-packs/${key}${version ? `?version=${version}` : ""}`}
          className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Pack
        </Link>

        <h1 className="text-2xl font-bold">Edit Policy Pack</h1>
        <p className="text-muted-foreground font-mono">{key}</p>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Pack Details</CardTitle>
            <CardDescription>Update policy pack configuration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData((current) => ({ ...current, name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="version">Version</Label>
                <Input
                  id="version"
                  value={formData.version}
                  onChange={(e) =>
                    setFormData((current) => ({ ...current, version: e.target.value }))
                  }
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((current) => ({ ...current, description: e.target.value }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="pack">Pack Configuration (JSON)</Label>
              <Textarea
                id="pack"
                className="min-h-96 font-mono text-sm"
                value={formData.pack}
                onChange={(e) => setFormData((current) => ({ ...current, pack: e.target.value }))}
                required
              />
            </div>
          </CardContent>
        </Card>

        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button type="submit">
            <Save className="mr-2 h-4 w-4" />
            Save Changes
          </Button>
        </div>
      </form>
    </div>
  );
}

function ClonePolicyPackDialog({
  sourceKey,
  sourceVersion,
  sourceName,
  sourceDescription,
}: {
  sourceKey: string;
  sourceVersion: string;
  sourceName: string;
  sourceDescription: string;
}) {
  const clonePack = useClonePolicyPack();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState({
    key: `${sourceKey}-custom`,
    version: "1.0",
    name: `${sourceName} Clone`,
    description: sourceDescription,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const created = await clonePack.mutateAsync({
        sourceKey,
        sourceVersion,
        data: {
          key: formData.key,
          version: formData.version,
          name: formData.name,
          description: formData.description || undefined,
        },
      });
      toast.success("Policy pack cloned");
      setOpen(false);
      router.push(`/policy-packs/${created.key}/edit?version=${created.version}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to clone policy pack");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Clone to Customize</CardTitle>
        <CardDescription>Create an editable custom pack from this built-in preset.</CardDescription>
      </CardHeader>
      <CardContent>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="w-full">
              <Copy className="mr-2 h-4 w-4" />
              Clone Preset
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Clone Policy Pack</DialogTitle>
              <DialogDescription>
                Create a new custom pack from {sourceKey}@{sourceVersion}.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="clone-key">Key</Label>
                  <Input
                    id="clone-key"
                    value={formData.key}
                    onChange={(e) =>
                      setFormData((current) => ({ ...current, key: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="clone-version">Version</Label>
                  <Input
                    id="clone-version"
                    value={formData.version}
                    onChange={(e) =>
                      setFormData((current) => ({ ...current, version: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="clone-name">Name</Label>
                  <Input
                    id="clone-name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData((current) => ({ ...current, name: e.target.value }))
                    }
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
      </CardContent>
    </Card>
  );
}
