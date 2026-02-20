"use client";

import { TraceList } from "@/components/traces/trace-list";
import { History } from "lucide-react";

export default function TracesPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <History className="h-8 w-8" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Decision Traces</h1>
          <p className="text-muted-foreground">
            Explore decision history and validate AI-generated context
          </p>
        </div>
      </div>

      <TraceList />
    </div>
  );
}
