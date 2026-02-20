"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  RefreshCw,
  CheckCircle,
  XCircle,
  Brain,
  User,
  Clock,
  AlertCircle,
  Target,
  GitCommit
} from "lucide-react";
import { api, type DecisionTrace, type ContextSuggestion } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { formatDate, formatDistanceToNow } from "@/lib/time";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";

interface TraceDetailProps {
  traceId: string;
}

export function TraceDetail({ traceId }: TraceDetailProps) {
  const router = useRouter();
  const [trace, setTrace] = useState<DecisionTrace | null>(null);
  const [suggestions, setSuggestions] = useState<ContextSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState<string | null>(null);
  const [customContext, setCustomContext] = useState("");

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [traceData, suggestionsData] = await Promise.all([
        api.traces.get(traceId),
        api.traces.getSuggestions(traceId),
      ]);
      setTrace(traceData);
      setSuggestions(suggestionsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch trace details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [traceId]);

  const handleFeedback = async (suggestionId: string, status: 'accepted' | 'rejected') => {
    try {
      setSubmittingFeedback(suggestionId);
      await api.traces.submitFeedback(suggestionId, status);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit feedback");
    } finally {
      setSubmittingFeedback(null);
    }
  };

  const getActionTypeBadge = (actionType: string) => {
    const colors: Record<string, string> = {
      CREATE: "bg-green-100 text-green-800",
      UPDATE: "bg-blue-100 text-blue-800",
      DELETE: "bg-red-100 text-red-800",
      TRANSITION: "bg-purple-100 text-purple-800",
    };
    const className = colors[actionType] || "bg-gray-100 text-gray-800";
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
        {actionType}
      </span>
    );
  };

  const getSuggestionSourceIcon = (source: string) => {
    if (source.startsWith('ai:')) {
      return <Brain className="h-4 w-4 text-purple-500" />;
    }
    return <Target className="h-4 w-4 text-blue-500" />;
  };

  if (loading && !trace) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Button variant="ghost" onClick={() => router.push('/traces')} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Traces
        </Button>
        <div className="p-4 text-sm text-red-800 bg-red-100 rounded-md">
          {error}
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="p-4">
        <Button variant="ghost" onClick={() => router.push('/traces')} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Traces
        </Button>
        <div className="p-4 text-sm text-amber-800 bg-amber-100 rounded-md">
          Trace not found
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push('/traces')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Decision Trace</h1>
            <p className="text-sm text-muted-foreground">{trace.id}</p>
          </div>
        </div>
        <Button variant="outline" size="icon" onClick={fetchData}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <GitCommit className="h-5 w-5" />
                <CardTitle>Action Details</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium">Action:</span>
                {getActionTypeBadge(trace.action_type)}
              </div>
              
              <Separator />
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Entity Type</label>
                  <p className="text-sm font-medium">{trace.entity_type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Entity ID</label>
                  <code className="text-xs bg-muted p-1 rounded">{trace.entity_id}</code>
                </div>
              </div>

              <Separator />

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {trace.actor_type}: {trace.actor_id}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {formatDistanceToNow(trace.timestamp)}
                  </span>
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                {formatDate(trace.timestamp)}
              </div>
            </CardContent>
          </Card>

          {/* Context Snapshot */}
          {trace.entity_snapshot && (
            <Card>
              <CardHeader>
                <CardTitle>Entity Snapshot</CardTitle>
                <CardDescription>State of the entity at the time of this action</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-md text-sm overflow-auto max-h-60">
                  {JSON.stringify(trace.entity_snapshot, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar - Suggestions */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <Brain className="h-5 w-5" />
                <CardTitle>AI Context Suggestions</CardTitle>
              </div>
              <CardDescription>
                Review and validate AI-generated context for this decision
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {suggestions.length === 0 ? (
                <div className="text-center py-6">
                  <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No suggestions available for this trace
                  </p>
                </div>
              ) : (
                suggestions.map((suggestion) => (
                  <div
                    key={suggestion.id}
                    className={`p-4 rounded-lg border ${
                      suggestion.status === 'accepted'
                        ? 'border-green-200 bg-green-50'
                        : suggestion.status === 'rejected'
                        ? 'border-red-200 bg-red-50'
                        : 'border-amber-200 bg-amber-50'
                    }`}
                  >
                    <div className="flex items-start gap-3 mb-3">
                      {getSuggestionSourceIcon(suggestion.source)}
                      <div className="flex-1">
                        <p className="text-sm">{suggestion.suggestion_text}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs text-muted-foreground">Confidence:</span>
                      <Progress value={suggestion.confidence * 100} className="h-2 flex-1" />
                      <span className="text-xs font-medium">
                        {Math.round(suggestion.confidence * 100)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        {suggestion.source}
                      </Badge>
                      
                      {suggestion.status === 'pending' ? (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleFeedback(suggestion.id, 'rejected')}
                            disabled={submittingFeedback === suggestion.id}
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleFeedback(suggestion.id, 'accepted')}
                            disabled={submittingFeedback === suggestion.id}
                          >
                            <CheckCircle className="h-4 w-4 mr-1" />
                            Accept
                          </Button>
                        </div>
                      ) : (
                        <Badge
                          className={
                            suggestion.status === 'accepted'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }
                        >
                          {suggestion.status === 'accepted' ? (
                            <><CheckCircle className="h-3 w-3 mr-1" /> Accepted</>
                          ) : (
                            <><XCircle className="h-3 w-3 mr-1" /> Rejected</>
                          )}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))
              )}

              {/* Custom Context Input */}
              <div className="pt-4 border-t">
                <h4 className="text-sm font-medium mb-2">Add Custom Context</h4>
                <Textarea
                  placeholder="Provide your own context for this decision..."
                  value={customContext}
                  onChange={(e) => setCustomContext(e.target.value)}
                  className="mb-2"
                />
                <Button 
                  size="sm" 
                  className="w-full"
                  disabled={!customContext.trim()}
                >
                  Submit Context
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Outcome Status */}
          {trace.outcome_status && (
            <Card>
              <CardHeader>
                <CardTitle>Outcome</CardTitle>
              </CardHeader>
              <CardContent>
                <Badge 
                  className={
                    trace.outcome_status === 'success' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }
                >
                  {trace.outcome_status}
                </Badge>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
