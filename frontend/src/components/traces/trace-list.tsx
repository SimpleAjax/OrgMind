"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
  RefreshCw, 
  Search,
  Filter,
  History,
  CheckCircle,
  AlertCircle,
  Brain,
  MoreHorizontal
} from "lucide-react";
import { api, type DecisionTrace } from "@/lib/api-client";
import { StatusBadge, getTraceStatusVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDistanceToNow, formatDate } from "@/lib/time";

interface TraceListProps {
  onRefresh?: () => void;
}

const actionTypeColors: Record<string, string> = {
  CREATE: "bg-green-100 text-green-800",
  UPDATE: "bg-blue-100 text-blue-800",
  DELETE: "bg-red-100 text-red-800",
  TRANSITION: "bg-purple-100 text-purple-800",
};

export function TraceList({ onRefresh }: TraceListProps) {
  const router = useRouter();
  const [traces, setTraces] = useState<DecisionTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [actionTypeFilter, setActionTypeFilter] = useState<string>("all");
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>("all");

  const fetchTraces = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const filters: { action_type?: string; entity_type?: string } = {};
      if (actionTypeFilter !== "all") filters.action_type = actionTypeFilter;
      if (entityTypeFilter !== "all") filters.entity_type = entityTypeFilter;
      
      const data = await api.traces.list(100, 0, filters);
      setTraces(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch traces");
    } finally {
      setLoading(false);
    }
  }, [actionTypeFilter, entityTypeFilter]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  const filteredTraces = traces.filter((trace) => {
    const matchesSearch = 
      trace.entity_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      trace.actor_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      trace.action_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      trace.entity_type.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const getActionTypeBadge = (actionType: string) => {
    const className = actionTypeColors[actionType] || "bg-gray-100 text-gray-800";
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
        {actionType}
      </span>
    );
  };

  const getTraceStatusDisplay = (trace: DecisionTrace) => {
    if (!trace.has_suggestions) {
      return (
        <div className="flex items-center gap-1 text-muted-foreground">
          <span className="text-xs">No AI context</span>
        </div>
      );
    }
    if (trace.validated_suggestion) {
      return (
        <div className="flex items-center gap-1 text-green-600">
          <CheckCircle className="h-3 w-3" />
          <span className="text-xs">Validated</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1 text-amber-600">
        <Brain className="h-3 w-3" />
        <span className="text-xs">AI Suggested</span>
      </div>
    );
  };

  // Extract unique entity types for filter
  const entityTypes = Array.from(new Set(traces.map(t => t.entity_type)));
  const actionTypes = Array.from(new Set(traces.map(t => t.action_type)));

  if (loading && traces.length === 0) {
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

      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search traces..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        
        <Select value={actionTypeFilter} onValueChange={setActionTypeFilter}>
          <SelectTrigger className="w-[140px]">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Action Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Actions</SelectItem>
            {actionTypes.map((type) => (
              <SelectItem key={type} value={type}>{type}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={entityTypeFilter} onValueChange={setEntityTypeFilter}>
          <SelectTrigger className="w-[140px]">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Entity Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Entities</SelectItem>
            {entityTypes.map((type) => (
              <SelectItem key={type} value={type}>{type}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button variant="outline" size="icon" onClick={fetchTraces}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Timestamp</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>AI Context</TableHead>
              <TableHead className="w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTraces.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  No traces found
                </TableCell>
              </TableRow>
            ) : (
              filteredTraces.map((trace) => (
                <TableRow 
                  key={trace.id} 
                  className="cursor-pointer" 
                  onClick={() => router.push(`/traces/${trace.id}`)}
                >
                  <TableCell>
                    <div className="text-sm">{formatDistanceToNow(trace.timestamp)}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatDate(trace.timestamp)}
                    </div>
                  </TableCell>
                  <TableCell>
                    {getActionTypeBadge(trace.action_type)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {trace.entity_type}
                      </Badge>
                      <span className="text-sm text-muted-foreground truncate max-w-[120px]">
                        {trace.entity_id}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">
                        {trace.actor_type}
                      </Badge>
                      <span className="text-sm truncate max-w-[100px]">
                        {trace.actor_id}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {getTraceStatusDisplay(trace)}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => router.push(`/traces/${trace.id}`)}>
                          <History className="h-4 w-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => router.push(`/objects/${trace.entity_id}`)}>
                          <Search className="h-4 w-4 mr-2" />
                          View Entity
                        </DropdownMenuItem>
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
