"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  RefreshCw,
  AlertCircle,
  User,
  Calendar
} from "lucide-react";
import { api, type PendingApproval } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow, formatDate, getCountdown } from "@/lib/time";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export function ApprovalList() {
  const router = useRouter();
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<PendingApproval | null>(null);
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.approvals.list();
      setApprovals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch approvals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
    // Poll every 10 seconds for new approvals
    const interval = setInterval(fetchApprovals, 10000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleSubmitDecision = async () => {
    if (!selectedApproval || !decision) return;

    try {
      setSubmitting(true);
      await api.approvals.submit(selectedApproval.id, {
        decision,
        reason: reason.trim() || undefined,
      });
      setSelectedApproval(null);
      setDecision(null);
      setReason("");
      fetchApprovals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit decision");
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickAction = (approval: PendingApproval, action: 'approve' | 'reject') => {
    setSelectedApproval(approval);
    setDecision(action);
  };

  const getCountdownDisplay = (timeoutAt?: string) => {
    if (!timeoutAt) return null;
    const countdown = getCountdown(timeoutAt);
    if (countdown.expired) return <span className="text-red-500 text-xs">Expired</span>;
    return (
      <span className="text-amber-600 text-xs">
        Expires in {countdown.hours}h {countdown.minutes}m
      </span>
    );
  };

  if (loading && approvals.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-4 text-sm text-red-800 bg-red-100 rounded-md flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Pending Approvals</h2>
          {approvals.length > 0 && (
            <Badge variant="secondary">{approvals.length}</Badge>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={fetchApprovals}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {approvals.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <CheckCircle className="h-12 w-12 text-green-500 mb-4" />
            <h3 className="text-lg font-semibold">All Caught Up!</h3>
            <p className="text-muted-foreground max-w-sm">
              You have no pending approvals. New approval requests will appear here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {approvals.map((approval) => (
            <Card key={approval.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base">{approval.title}</CardTitle>
                    <CardDescription>{approval.workflow_name}</CardDescription>
                  </div>
                  <Clock className="h-5 w-5 text-muted-foreground" />
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-3">
                {approval.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {approval.description}
                  </p>
                )}
                
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <User className="h-4 w-4" />
                    <span>Requested by {approval.requested_by || 'System'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Calendar className="h-4 w-4" />
                    <span>{formatDistanceToNow(approval.requested_at)}</span>
                  </div>
                </div>

                {getCountdownDisplay(approval.timeout_at)}
              </CardContent>
              <CardFooter className="gap-2 pt-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => handleQuickAction(approval, 'reject')}
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Reject
                </Button>
                <Button
                  className="flex-1"
                  onClick={() => handleQuickAction(approval, 'approve')}
                >
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Approve
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Decision Dialog */}
      <Dialog open={!!selectedApproval} onOpenChange={() => setSelectedApproval(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {decision === 'approve' ? 'Approve' : 'Reject'} Request
            </DialogTitle>
            <DialogDescription>
              {selectedApproval?.title}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {selectedApproval?.context && (
              <div className="bg-muted p-3 rounded-md">
                <h4 className="text-sm font-medium mb-2">Context</h4>
                <pre className="text-xs overflow-auto">
                  {JSON.stringify(selectedApproval.context, null, 2)}
                </pre>
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="reason">Reason (Optional)</Label>
              <Textarea
                id="reason"
                placeholder={decision === 'approve' ? "Add an optional note..." : "Please provide a reason for rejection..."}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedApproval(null)}>
              Cancel
            </Button>
            <Button
              variant={decision === 'reject' ? 'destructive' : 'default'}
              onClick={handleSubmitDecision}
              disabled={submitting}
            >
              {submitting ? 'Submitting...' : decision === 'approve' ? 'Approve' : 'Reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
