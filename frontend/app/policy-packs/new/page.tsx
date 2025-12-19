"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useCreatePolicyPack } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

const defaultPack = {
  meta: {
    version: "1.0",
    label: "Custom Policy Pack",
    description: "A custom policy pack",
  },
  defaults: {
    models: {
      exec: "codex-5.1",
      qa: "codex-5.1",
      planning: "codex-5.1",
    },
  },
  requirements: {
    steps: {
      required_sections: ["Context", "Task", "Output Specification"],
    },
  },
  clarifications: [],
  enforcement: {
    mode: "warn",
  },
}

export default function NewPolicyPackPage() {
  const router = useRouter()
  const [key, setKey] = useState("")
  const [version, setVersion] = useState("1.0")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [packJson, setPackJson] = useState(JSON.stringify(defaultPack, null, 2))
  const [error, setError] = useState("")

  const createPack = useCreatePolicyPack()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    try {
      const pack = JSON.parse(packJson)
      await createPack.mutateAsync({
        key,
        version,
        name,
        description,
        pack,
      })
      router.push("/policy-packs")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create policy pack")
    }
  }

  return (
    <div className="container py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/policy-packs">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Policy Packs
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Create Policy Pack</h1>
            <p className="text-sm text-muted-foreground">Define a new policy pack for your projects</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card className="p-6">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="key">Key *</Label>
                  <Input
                    id="key"
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                    placeholder="my-custom-pack"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="version">Version *</Label>
                  <Input
                    id="version"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    placeholder="1.0"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Custom Pack"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="A description of what this policy pack enforces"
                  rows={3}
                />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="space-y-3">
              <Label>Policy Pack JSON *</Label>
              <Textarea
                value={packJson}
                onChange={(e) => setPackJson(e.target.value)}
                className="font-mono text-xs"
                rows={20}
                placeholder={JSON.stringify(defaultPack, null, 2)}
              />
            </div>
          </Card>

          {error && (
            <Card className="p-4 border-destructive">
              <p className="text-sm text-destructive">{error}</p>
            </Card>
          )}

          <div className="flex justify-end gap-3">
            <Link href="/policy-packs">
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={createPack.isPending}>
              {createPack.isPending ? "Creating..." : "Create Policy Pack"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
