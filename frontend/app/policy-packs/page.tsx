"use client"

import type React from "react"

import { useState } from "react"
import { usePolicyPacks, useCreatePolicyPack } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { StatusPill } from "@/components/ui/status-pill"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { CodeBlock } from "@/components/ui/code-block"
import { Plus, Shield, ChevronRight } from "lucide-react"
import { toast } from "sonner"
import type { PolicyPack } from "@/lib/api/types"

export default function PolicyPacksPage() {
  const { data: packs, isLoading } = usePolicyPacks()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [selectedPack, setSelectedPack] = useState<PolicyPack | null>(null)

  if (isLoading) return <LoadingState message="Loading policy packs..." />

  return (
    <div className="container py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Policy Packs</h1>
          <p className="text-muted-foreground">Manage policy packs for protocol governance</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Pack
            </Button>
          </DialogTrigger>
          <CreatePolicyPackDialog onClose={() => setIsCreateOpen(false)} />
        </Dialog>
      </div>

      {!packs || packs.length === 0 ? (
        <EmptyState
          icon={Shield}
          title="No policy packs"
          description="Create your first policy pack to define governance rules."
          action={
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Pack
            </Button>
          }
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <h3 className="font-semibold">Available Packs</h3>
            {packs.map((pack) => (
              <Card
                key={pack.id}
                className={`cursor-pointer transition-colors ${selectedPack?.id === pack.id ? "border-primary" : "hover:border-primary/50"}`}
                onClick={() => setSelectedPack(pack)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-mono">{pack.key}</CardTitle>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <CardDescription>{pack.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="font-mono text-muted-foreground">v{pack.version}</span>
                    <StatusPill status={pack.status === "active" ? "completed" : "pending"} size="sm" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div>
            {selectedPack ? (
              <Card>
                <CardHeader>
                  <CardTitle>{selectedPack.name}</CardTitle>
                  <CardDescription>
                    {selectedPack.key}@{selectedPack.version}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {selectedPack.description && (
                    <p className="text-sm text-muted-foreground">{selectedPack.description}</p>
                  )}
                  <CodeBlock code={selectedPack.pack} title="Pack Configuration" maxHeight="400px" />
                </CardContent>
              </Card>
            ) : (
              <div className="flex items-center justify-center h-64 border border-dashed rounded-lg">
                <p className="text-muted-foreground">Select a pack to view details</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function CreatePolicyPackDialog({ onClose }: { onClose: () => void }) {
  const createPack = useCreatePolicyPack()
  const [formData, setFormData] = useState({
    key: "",
    version: "1.0",
    name: "",
    description: "",
    pack: "{}",
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const packJson = JSON.parse(formData.pack)
      await createPack.mutateAsync({
        key: formData.key,
        version: formData.version,
        name: formData.name,
        description: formData.description || undefined,
        pack: packJson,
      })
      toast.success("Policy pack created successfully")
      onClose()
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON in pack configuration")
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to create pack")
      }
    }
  }

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>Create Policy Pack</DialogTitle>
        <DialogDescription>Create a new policy pack for protocol governance.</DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <div className="space-y-4 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="key">Key</Label>
              <Input
                id="key"
                placeholder="my-policy-pack"
                value={formData.key}
                onChange={(e) => setFormData((p) => ({ ...p, key: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="version">Version</Label>
              <Input
                id="version"
                placeholder="1.0"
                value={formData.version}
                onChange={(e) => setFormData((p) => ({ ...p, version: e.target.value }))}
                required
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="My Policy Pack"
              value={formData.name}
              onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              placeholder="Description of the policy pack..."
              value={formData.description}
              onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pack">Pack Configuration (JSON)</Label>
            <Textarea
              id="pack"
              className="font-mono text-sm min-h-48"
              placeholder='{ "defaults": {}, "requirements": {} }'
              value={formData.pack}
              onChange={(e) => setFormData((p) => ({ ...p, pack: e.target.value }))}
              required
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={createPack.isPending}>
            {createPack.isPending ? "Creating..." : "Create Pack"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  )
}
