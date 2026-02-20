"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
  Play, 
  Square, 
  RefreshCw, 
  MoreHorizontal,
  Search,
  Filter
} from "lucide-react";
import { api, type WorkflowExecution } from "@/lib/api-client";
import { StatusBadge, getWorkflowStatusVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDistanceToNow } from "@/lib/time";

interface WorkflowListProps {
  onRefresh?: () => void;
}

export function WorkflowList({ onRefresh }: WorkflowListProps) {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<WorkflowExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const fetchWorkflows = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.workflows.list(100, 0);
      setWorkflows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch workflows");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
    // Poll every 5 seconds for running workflows
    const interval = setInterval(() => {
      const hasRunning = workflows.some(w => w.status === 'RUNNING');
      if (hasRunning) {
        fetchWorkflows();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchWorkflows, workflows]);

  const handleCancel = async (workflowId: string) => {
    try {
      await api.workflows.cancel(workflowId);
      fetchWorkflows();
      onRefresh?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel workflow");
    }
  };

  const filteredWorkflows = workflows.filter((workflow) => {
    const matchesSearch = workflow.workflow_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         workflow.workflow_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter ? workflow.status === statusFilter : true;
    return matchesSearch && matchesStatus;
  });

  const statusOptions = ['RUNNING', 'COMPLETED', 'FAILED', 'CANCELED', 'TERMINATED', 'TIMED_OUT'];

  if (loading && workflows.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-4 text-sm text-red-800 bg-red-100 rounded-md">
          {error}
        </div>
      )}
      
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search workflows..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Filter className="h-4 w-4" />
              {statusFilter || "All Statuses"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => setStatusFilter(null)}>
              All Statuses
            </DropdownMenuItem>
            {statusOptions.map((status) => (
              <DropdownMenuItem key={status} onClick={() => setStatusFilter(status)}>
                {status}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Button variant="outline" size="icon" onClick={fetchWorkflows}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Workflow</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Task Queue</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredWorkflows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No workflows found
                </TableCell>
              </TableRow>
            ) : (
              filteredWorkflows.map((workflow) => (
                <TableRow key={workflow.workflow_id} className="cursor-pointer" onClick={() => router.push(`/workflows/${workflow.workflow_id}`)}>
                  <TableCell>
                    <div className="font-medium">{workflow.workflow_name}</div>
                    <div className="text-sm text-muted-foreground">{workflow.workflow_id}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge 
                      variant={getWorkflowStatusVariant(workflow.status)} 
                      label={workflow.status} 
                    />
                  </TableCell>
                  <TableCell>
                    {formatDistanceToNow(workflow.started_at)}
                  </TableCell>
                  <TableCell>{workflow.task_queue}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => router.push(`/workflows/${workflow.workflow_id}`)}>
                          <Play className="h-4 w-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                        {workflow.status === 'RUNNING' && (
                          <DropdownMenuItem 
                            onClick={() => handleCancel(workflow.workflow_id)}
                            className="text-red-600"
                          >
                            <Square className="h-4 w-4 mr-2" />
                            Cancel
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
