import { use } from "react";
import { redirect } from "next/navigation";

export default function SprintBoardRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  redirect(`/projects/${id}/execution`);
}
