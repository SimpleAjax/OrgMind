"use client";

import { useParams } from "next/navigation";
import { WorkflowDetail } from "@/components/workflows/workflow-detail";

export default function WorkflowDetailPage() {
  const params = useParams();
  const workflowId = params.id as string;

  return <WorkflowDetail workflowId={workflowId} />;
}
