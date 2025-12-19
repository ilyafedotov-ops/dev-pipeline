"use client"
import { use } from "react"

import Link from "next/link"
import { usePolicyPacks } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { LoadingState } from "@/components/ui/loading-state"
import { CodeBlock } from "@/components/ui/code-block"
import { StatusPill } from "@/components/ui/status-pill"
import { ArrowLeft, Edit } from "lucide-react"
import { formatDateTime } from "@/lib/format"

export default function PolicyPackDetailPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params)
  const { data: packs, isLoading } = usePolicyPacks()

  if (isLoading) return <LoadingState message="Loading policy pack..." />

  const pack = packs?.find((p) => p.key === key)

  if (!pack) {
    return (
      <div className="container py-8">
        <p className="text-muted-foreground">Policy pack not found</p>
      </div>
    )
  }

  return (
    <div className="container py-8">
      <div className="mb-6">
        <Link
          href="/policy-packs"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Policy Packs
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold font-mono">{pack.key}</h1>
            <p className="text-muted-foreground mt-1">{pack.name}</p>
          </div>
          <Button variant="outline" asChild>
            <Link href={`/policy-packs/${key}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-6 mb-6 md:grid-cols-3">
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

      {pack.description && (
        <Card className="mb-6">
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
  )
}
