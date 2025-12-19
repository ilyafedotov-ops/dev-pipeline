"use client"
import { use } from "react"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { usePolicyPacks } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { LoadingState } from "@/components/ui/loading-state"
import { ArrowLeft, Save } from "lucide-react"
import { toast } from "sonner"

export default function EditPolicyPackPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params)
  const router = useRouter()
  const { data: packs, isLoading } = usePolicyPacks()

  const pack = packs?.find((p) => p.key === key)

  const [formData, setFormData] = useState({
    name: pack?.name || "",
    description: pack?.description || "",
    version: pack?.version || "",
    pack: typeof pack?.pack === "string" ? pack.pack : JSON.stringify(pack?.pack, null, 2),
  })

  if (isLoading) return <LoadingState message="Loading policy pack..." />

  if (!pack) {
    return (
      <div className="container py-8">
        <p className="text-muted-foreground">Policy pack not found</p>
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      JSON.parse(formData.pack) // Validate JSON
      toast.success("Policy pack updated successfully")
      router.push(`/policy-packs/${key}`)
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON in pack configuration")
      } else {
        toast.error("Failed to update policy pack")
      }
    }
  }

  return (
    <div className="container py-8">
      <div className="mb-6">
        <Link
          href={`/policy-packs/${key}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
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
                  onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="version">Version</Label>
                <Input
                  id="version"
                  value={formData.version}
                  onChange={(e) => setFormData((p) => ({ ...p, version: e.target.value }))}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="pack">Pack Configuration (JSON)</Label>
              <Textarea
                id="pack"
                className="font-mono text-sm min-h-96"
                value={formData.pack}
                onChange={(e) => setFormData((p) => ({ ...p, pack: e.target.value }))}
                required
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-2 mt-6">
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
  )
}
