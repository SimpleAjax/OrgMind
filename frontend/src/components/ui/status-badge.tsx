"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const statusBadgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-slate-100 text-slate-800",
        success: "bg-green-100 text-green-800",
        warning: "bg-yellow-100 text-yellow-800",
        error: "bg-red-100 text-red-800",
        info: "bg-blue-100 text-blue-800",
        pending: "bg-amber-100 text-amber-800",
        running: "bg-blue-100 text-blue-800 animate-pulse",
        completed: "bg-green-100 text-green-800",
        failed: "bg-red-100 text-red-800",
        canceled: "bg-gray-100 text-gray-800",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  label?: string;
}

export function StatusBadge({ className, variant, label, ...props }: StatusBadgeProps) {
  return (
    <span
      className={cn(statusBadgeVariants({ variant }), className)}
      {...props}
    >
      {label || props.children}
    </span>
  );
}

// Helper to map workflow status to badge variant
export function getWorkflowStatusVariant(status: string) {
  switch (status) {
    case 'RUNNING':
      return 'running';
    case 'COMPLETED':
      return 'completed';
    case 'FAILED':
      return 'failed';
    case 'CANCELED':
    case 'TERMINATED':
      return 'canceled';
    case 'TIMED_OUT':
      return 'error';
    default:
      return 'pending';
  }
}

// Helper to map approval status to badge variant
export function getApprovalStatusVariant(status: string) {
  switch (status) {
    case 'approved':
      return 'success';
    case 'rejected':
      return 'error';
    case 'pending':
      return 'pending';
    default:
      return 'default';
  }
}

// Helper to map trace validation status to badge variant
export function getTraceStatusVariant(hasSuggestions: boolean, validated: boolean) {
  if (!hasSuggestions) return 'default';
  if (validated) return 'success';
  return 'warning';
}
