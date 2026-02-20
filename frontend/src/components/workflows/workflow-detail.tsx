"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  Square, 
  Play, 
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import { api, type WorkflowStatus } from "@/lib/api-client";
import { StatusBadge, getWorkflowStatusVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatDate, formatDistanceToNow } from "@/lib/time";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface WorkflowDetailProps {
  workflowId: string;
}

export function WorkflowDetail({ workflowId }: WorkflowDetailProps) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<WorkflowStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const fetchWorkflow = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.workflows.get(workflowId);
      setWorkflow(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch workflow");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflow();
    // Poll every 3 seconds for running workflows
    const interval = setInterval(() => {
      if (workflow?.status === 'RUNNING') {
        fetchWorkflow();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [workflowId, workflow?.status]);

  const handleCancel = async () => {
    try {
      setCancelling(true);
      await api.workflows.cancel(workflowId);
      setCancelDialogOpen(false);
      fetchWorkflow();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel workflow");
    } finally {
      setCancelling(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'RUNNING':
        return <Clock className="h-5 w-5 text-blue-500" />;
      case 'COMPLETED':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'FAILED':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />;
    }
  };

  if (loading && !workflow) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Button variant="ghost" onClick={() => router.push('/workflows')} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workflows
        </Button>
        <div className="p-4 text-sm text-red-800 bg-red-100 rounded-md">
          {error}
        </div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="p-4">
        <Button variant="ghost" onClick={() => router.push('/workflows')} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workflows
        </Button>
        <div className="p-4 text-sm text-amber-800 bg-amber-100 rounded-md">
          Workflow not found
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push('/workflows')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold">Workflow Details</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={fetchWorkflow}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          {workflow.status === 'RUNNING' && (
            <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive">
                  <Square className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Cancel Workflow</DialogTitle>
                  <DialogDescription>
                    Are you sure you want to cancel this workflow? This action cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
                    Keep Running
                  </Button>
                  <Button variant="destructive" onClick={handleCancel} disabled={cancelling}>
                    {cancelling ? 'Cancelling...' : 'Cancel Workflow'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            {getStatusIcon(workflow.status)}
            <CardTitle>Status Overview</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Status:</span>
            <StatusBadge 
              variant={getWorkflowStatusVariant(workflow.status)} 
              label={workflow.status} 
            />
          </div>
          
          <Separator />
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Workflow ID</label>
              <p className="text-sm font-mono">{workflow.workflow_id}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Run ID</label>
              <p className="text-sm font-mono">{workflow.run_id}</p>
            </div>
          </div>

          {workflow.result !== undefined && workflow.result !== null && (
            <>
              <Separator />
              <div>
                <label className="text-sm font-medium text-muted-foreground">Result</label>
                <pre className="mt-2 p-4 bg-muted rounded-md text-sm overflow-auto">
                  {JSON.stringify(workflow.result, null, 2)}
                </pre>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Timeline visualization placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Execution Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
                <Play className="h-4 w-4 text-white" />
              </div>
              <span className="text-xs mt-1">Started</span>
            </div>
            <div className="flex-1 h-0.5 bg-muted" />
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                workflow.status === 'RUNNING' ? 'bg-blue-500 animate-pulse' : 
                workflow.status === 'COMPLETED' ? 'bg-green-500' : 'bg-gray-300'
              }`}>
                {workflow.status === 'RUNNING' ? (
                  <Clock className="h-4 w-4 text-white" />
                ) : workflow.status === 'COMPLETED' ? (
                  <CheckCircle className="h-4 w-4 text-white" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-white" />
                )}
              </div>
              <span className="text-xs mt-1">
                {workflow.status === 'RUNNING' ? 'Running' : 
                 workflow.status === 'COMPLETED' ? 'Completed' : 'Ended'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
