"use client"
import { use } from "react"

import { useProtocolDetail } from "@/lib/api"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { PolicyTab } from "../components/policy-tab"

export default function ProtocolPolicyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = params
  const protocolId = Number.parseInt(id)
  const { data: protocol, isLoading } = useProtocolDetail(protocolId)

  if (isLoading) {
    return <LoadingState />
  }

  if (!protocol) {
    return <EmptyState title="Protocol not found" />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/protocols/${id}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Protocol
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{protocol.protocol_name} - Policy</h1>
          <p className="text-sm text-muted-foreground">Protocol #{protocol.id}</p>
        </div>
      </div>

      <PolicyTab protocolId={protocolId} />
    </div>
  )
}
