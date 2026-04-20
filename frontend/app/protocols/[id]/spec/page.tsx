"use client";
import { use } from "react";
import Link from "next/link";

import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useProtocolDetail } from "@/lib/api";

import { SpecTab } from "../components/spec-tab";

export default function ProtocolSpecPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const protocolId = Number.parseInt(id);
  const { data: protocol, isLoading } = useProtocolDetail(protocolId);

  if (isLoading) {
    return <LoadingState />;
  }

  if (!protocol) {
    return <EmptyState title="Protocol not found" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/protocols/${id}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Protocol
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{protocol.protocol_name} - Spec</h1>
          <p className="text-muted-foreground text-sm">Protocol #{protocol.id}</p>
        </div>
      </div>

      <SpecTab protocolId={protocolId} />
    </div>
  );
}
