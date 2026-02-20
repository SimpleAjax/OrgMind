"use client";

import { useState } from "react";
import { GraphViewer } from "@/components/graph/graph-viewer";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, Share2 } from "lucide-react";
import { api, type GraphNode } from "@/lib/api-client";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSearchParams, useRouter } from "next/navigation";

export default function GraphPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialNodeId = searchParams.get("nodeId") || undefined;
  
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<GraphNode[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [depth, setDepth] = useState("2");

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      setSearching(true);
      const results = await api.graph.search(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setSearching(false);
    }
  };

  const handleNodeSelect = (node: GraphNode) => {
    setSelectedNode(node);
    setSearchResults([]);
    setSearchQuery(node.label);
    // Update URL with node ID
    router.push(`/graph?nodeId=${node.id}`);
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Share2 className="h-6 w-6" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Graph Explorer</h1>
              <p className="text-sm text-muted-foreground">
                Visualize relationships and connections between entities
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search for entities..."
              className="pl-8"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-md shadow-lg z-50">
                {searchResults.map((node) => (
                  <button
                    key={node.id}
                    className="w-full px-4 py-2 text-left hover:bg-accent flex items-center gap-2"
                    onClick={() => handleNodeSelect(node)}
                  >
                    <span className="text-xs font-medium px-2 py-0.5 bg-muted rounded">
                      {node.type}
                    </span>
                    <span>{node.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          
          <Button onClick={handleSearch} disabled={searching}>
            {searching ? "Searching..." : "Search"}
          </Button>

          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Depth:</span>
            <Select value={depth} onValueChange={setDepth}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1-hop</SelectItem>
                <SelectItem value="2">2-hop</SelectItem>
                <SelectItem value="3">3-hop</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 min-h-0">
        <div className="h-full border rounded-lg overflow-hidden">
          <GraphViewer 
            initialNodeId={initialNodeId} 
            onNodeSelect={setSelectedNode}
          />
        </div>
      </div>
    </div>
  );
}
