"use client";

import { useParams } from "next/navigation";
import { TraceDetail } from "@/components/traces/trace-detail";

export default function TraceDetailPage() {
  const params = useParams();
  const traceId = params.id as string;

  return <TraceDetail traceId={traceId} />;
}
