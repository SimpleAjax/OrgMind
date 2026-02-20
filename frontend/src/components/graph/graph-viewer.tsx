"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize, 
  Move,
  X,
  Search,
  ChevronRight,
  Loader2
} from "lucide-react";
import { api, type GraphData, type GraphNode, type GraphEdge } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface GraphViewerProps {
  initialNodeId?: string;
  onNodeSelect?: (node: GraphNode) => void;
}

// Color mapping for different node types
const nodeTypeColors: Record<string, string> = {
  user: "bg-blue-500",
  project: "bg-green-500",
  task: "bg-purple-500",
  team: "bg-orange-500",
  document: "bg-pink-500",
  default: "bg-gray-500",
};

export function GraphViewer({ initialNodeId, onNodeSelect }: GraphViewerProps) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const loadGraph = useCallback(async (nodeId: string, depth = 2) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.graph.get(nodeId, depth);
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialNodeId) {
      loadGraph(initialNodeId);
    }
  }, [initialNodeId, loadGraph]);

  const handleZoomIn = () => setScale(s => Math.min(s * 1.2, 3));
  const handleZoomOut = () => setScale(s => Math.max(s / 1.2, 0.3));
  const handleFit = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === containerRef.current || (e.target as HTMLElement).closest('.graph-canvas')) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    onNodeSelect?.(node);
  };

  const handleNodeDoubleClick = (node: GraphNode) => {
    loadGraph(node.id);
  };

  // Simple force-directed layout simulation
  const calculateNodePositions = () => {
    const width = containerRef.current?.clientWidth || 800;
    const height = containerRef.current?.clientHeight || 600;
    const centerX = width / 2;
    const centerY = height / 2;

    const positions: Record<string, { x: number; y: number }> = {};
    const nodeCount = graphData.nodes.length;

    graphData.nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / nodeCount;
      const radius = Math.min(width, height) * 0.3;
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    });

    return positions;
  };

  const nodePositions = calculateNodePositions();

  const getConnectedNodes = (nodeId: string) => {
    return graphData.edges
      .filter(e => e.source === nodeId || e.target === nodeId)
      .map(e => e.source === nodeId ? e.target : e.source);
  };

  return (
    <div className="flex h-full gap-4">
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="flex items-center gap-2 p-2 border-b">
          <Button variant="outline" size="icon" onClick={handleZoomOut}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground min-w-[60px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <Button variant="outline" size="icon" onClick={handleZoomIn}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={handleFit}>
            <Maximize className="h-4 w-4" />
          </Button>
          <div className="flex-1" />
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Move className="h-4 w-4" />
            <span>Drag to pan • Double-click node to expand</span>
          </div>
        </div>

        {/* Graph Canvas */}
        <div
          ref={containerRef}
          className="flex-1 relative overflow-hidden bg-muted/30 cursor-move graph-canvas"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="absolute top-4 left-4 right-4 p-4 text-sm text-red-800 bg-red-100 rounded-md z-10">
              {error}
            </div>
          )}

          <div
            className="absolute inset-0 transition-transform"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            }}
          >
            {/* Edges */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {graphData.edges.map((edge) => {
                const source = nodePositions[edge.source];
                const target = nodePositions[edge.target];
                if (!source || !target) return null;
                return (
                  <g key={edge.id}>
                    <line
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke="#94a3b8"
                      strokeWidth={2}
                    />
                    <text
                      x={(source.x + target.x) / 2}
                      y={(source.y + target.y) / 2}
                      textAnchor="middle"
                      className="text-xs fill-muted-foreground"
                      style={{ fontSize: '10px' }}
                    >
                      {edge.type}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Nodes */}
            {graphData.nodes.map((node) => {
              const pos = nodePositions[node.id];
              if (!pos) return null;
              return (
                <div
                  key={node.id}
                  className={`absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all ${
                    selectedNode?.id === node.id ? 'scale-110' : ''
                  }`}
                  style={{ left: pos.x, top: pos.y }}
                  onClick={() => handleNodeClick(node)}
                  onDoubleClick={() => handleNodeDoubleClick(node)}
                >
                  <div
                    className={`w-12 h-12 rounded-full ${
                      nodeTypeColors[node.type] || nodeTypeColors.default
                    } flex items-center justify-center shadow-lg border-2 ${
                      selectedNode?.id === node.id ? 'border-primary' : 'border-white'
                    }`}
                  >
                    <span className="text-white text-xs font-bold">
                      {node.label.slice(0, 2).toUpperCase()}
                    </span>
                  </div>
                  <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap">
                    <span className="text-xs font-medium bg-background px-2 py-0.5 rounded shadow">
                      {node.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {graphData.nodes.length === 0 && !loading && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  Search for a node to start exploring the graph
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Node Details Panel */}
      {selectedNode && (
        <Card className="w-80 flex-shrink-0">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-lg">{selectedNode.label}</CardTitle>
                <Badge variant="secondary" className="mt-1">
                  {selectedNode.type}
                </Badge>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setSelectedNode(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-1">ID</h4>
              <code className="text-xs bg-muted p-1 rounded">{selectedNode.id}</code>
            </div>
            
            {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Properties</h4>
                <ScrollArea className="h-40">
                  <div className="space-y-1">
                    {Object.entries(selectedNode.properties).map(([key, value]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{key}:</span>
                        <span className="font-medium">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Connected Nodes</h4>
              <div className="space-y-1">
                {getConnectedNodes(selectedNode.id).map((nodeId) => {
                  const connectedNode = graphData.nodes.find(n => n.id === nodeId);
                  if (!connectedNode) return null;
                  return (
                    <div
                      key={nodeId}
                      className="flex items-center gap-2 p-2 hover:bg-muted rounded cursor-pointer"
                      onClick={() => handleNodeClick(connectedNode)}
                    >
                      <div className={`w-3 h-3 rounded-full ${nodeTypeColors[connectedNode.type] || nodeTypeColors.default}`} />
                      <span className="text-sm flex-1">{connectedNode.label}</span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  );
                })}
              </div>
            </div>

            <Button 
              className="w-full" 
              onClick={() => loadGraph(selectedNode.id)}
            >
              Expand Neighbors
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
