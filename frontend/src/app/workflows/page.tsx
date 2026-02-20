"use client";

import { WorkflowList } from "@/components/workflows/workflow-list";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { useRouter } from "next/navigation";

export default function WorkflowsPage() {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [workflowName, setWorkflowName] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartWorkflow = async () => {
    if (!workflowName.trim()) return;
    
    try {
      setStarting(true);
      setError(null);
      const result = await api.workflows.start({
        workflow_name: workflowName,
        args: [],
        task_queue: "default-queue",
      });
      setDialogOpen(false);
      setWorkflowName("");
      router.push(`/workflows/${result.workflow_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start workflow");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Monitor and manage your workflow executions
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Start Workflow
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Start New Workflow</DialogTitle>
              <DialogDescription>
                Enter the workflow name to start a new execution.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {error && (
                <div className="p-3 text-sm text-red-800 bg-red-100 rounded-md">
                  {error}
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="workflow-name">Workflow Name</Label>
                <Input
                  id="workflow-name"
                  placeholder="e.g., EmployeeOnboarding"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleStartWorkflow} 
                disabled={!workflowName.trim() || starting}
              >
                {starting ? 'Starting...' : 'Start Workflow'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <WorkflowList />
    </div>
  );
}
