"use client";
import { use, useEffect } from "react";
import { useRouter } from "next/navigation";

import { LoadingState } from "@/components/ui/loading-state";

export default function ProjectProtocolsRedirectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  useEffect(() => {
    router.replace(`/projects/${id}?tab=protocols`);
  }, [id, router]);

  return <LoadingState message="Redirecting..." />;
}
