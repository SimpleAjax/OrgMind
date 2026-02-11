"""
Query Service - Unified query layer for PostgreSQL and Neo4j.

This service provides a seamless interface for querying the organizational
knowledge graph, combining the structural strengths of Neo4j with the
relational data of PostgreSQL.
"""

from typing import List, Dict, Any, Optional, Set
import logging
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session
from neo4j.exceptions import Neo4jError

from orgmind.storage.models import ObjectModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.graph.neo4j_adapter import Neo4jAdapter


logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """Represents a node in the graph result."""
    id: str
    type_id: str
    data: Dict[str, Any]
    # Enriched data from PostgreSQL
    details: Optional[ObjectModel] = None


@dataclass
class GraphEdge:
    """Represents an edge in the graph result."""
    id: str
    type_id: str
    source_id: str
    target_id: str
    data: Dict[str, Any]


@dataclass
class GraphResult:
    """Container for graph query results."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphQueryService:
    """
    Service for executing hybrid queries across Neo4j and PostgreSQL.
    """

    def __init__(
        self,
        neo4j_adapter: Neo4jAdapter,
        object_repo: ObjectRepository,
    ):
        """
        Initialize the query service.
        
        Args:
            neo4j_adapter: Adapter for Neo4j operations
            object_repo: Repository for fetching object details
        """
        self.neo4j = neo4j_adapter
        self.object_repo = object_repo

    def get_neighbors(
        self,
        session: Session,
        object_id: str,
        depth: int = 1,
        direction: str = "outgoing",
        limit: int = 50,
    ) -> GraphResult:
        """
        Get neighboring objects and relationships.
        
        Args:
            session: SQLAlchemy session for PostgreSQL queries
            object_id: ID of the start object
            depth: Traversal depth (default: 1)
            direction: Direction of relationships ('incoming', 'outgoing', 'both')
            limit: Maximum number of neighbors to return
            
        Returns:
            GraphResult containing enriched nodes and edges
        """
        # Determine relationship direction syntax
        # We match a path (start)-[...]->(end) and then UNWIND relationships
        # Note: Cypher direction depends on arrow placement
        
        rel_pattern = "-[:LINK*1..%d]->" % depth
        if direction == "incoming":
            rel_pattern = "<-[:LINK*1..%d]-" % depth
        elif direction == "both":
            rel_pattern = "-[:LINK*1..%d]-" % depth
            
        # We query for paths, then unwind relationships to get distinct edges and nodes
        query = f"""
        MATCH p = (start:Object {{id: $start_id}}){rel_pattern}(end:Object)
        UNWIND relationships(p) as r
        WITH start, end, r, startNode(r) as source, endNode(r) as target
        RETURN DISTINCT
            source.id as source_id, 
            source.type_id as source_type_id,
            source.data as source_data,
            target.id as target_id, 
            target.type_id as target_type_id,
            target.data as target_data,
            r.id as link_id, 
            r.type_id as link_type_id, 
            r.data as link_data
        LIMIT $limit
        """
        
        try:
            results = self.neo4j.execute_read(
                query,
                {"start_id": object_id, "limit": limit}
            )
            
            return self._process_flat_results(session, results)

        except Neo4jError as e:
            logger.error(f"Graph query failed: {e}")
            raise

    def find_shortest_path(
        self,
        session: Session,
        start_id: str,
        end_id: str,
        max_depth: int = 5
    ) -> GraphResult:
        """
        Find shortest path between two objects.
        
        Args:
            session: SQLAlchemy session
            start_id: Start object ID
            end_id: End object ID
            max_depth: Maximum path length
            
        Returns:
            GraphResult with the path
        """
        query = f"""
        MATCH p = shortestPath((start:Object {{id: $start_id}})-[*..{max_depth}]-(end:Object {{id: $end_id}}))
        UNWIND relationships(p) as r
        WITH start, end, r, startNode(r) as source, endNode(r) as target
        RETURN DISTINCT
            source.id as source_id, 
            source.type_id as source_type_id,
            source.data as source_data,
            target.id as target_id, 
            target.type_id as target_type_id,
            target.data as target_data,
            r.id as link_id, 
            r.type_id as link_type_id, 
            r.data as link_data
        """
        
        try:
            results = self.neo4j.execute_read(
                query,
                {"start_id": start_id, "end_id": end_id}
            )
            
            return self._process_flat_results(session, results)
            
        except Neo4jError as e:
            logger.error(f"Shortest path query failed: {e}")
            raise

    def _parse_json(self, value: Any) -> Dict:
        """Helper to parse potentially serialized JSON."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return value if isinstance(value, dict) else {}

    def _process_flat_results(self, session: Session, results: List[Dict[str, Any]]) -> GraphResult:
        """
        Process flat Cypher results (source, target, link) into GraphResult.
        Fetch full object details from PostgreSQL.
        """
        nodes_map: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []
        object_ids_to_fetch: Set[str] = set()
        
        for row in results:
            # Source Node
            s_id = row.get("source_id")
            if s_id and s_id not in nodes_map:
                s_data = self._parse_json(row.get("source_data"))
                nodes_map[s_id] = GraphNode(
                    id=s_id, 
                    type_id=row.get("source_type_id", ""), 
                    data=s_data
                )
                object_ids_to_fetch.add(s_id)
            
            # Target Node
            t_id = row.get("target_id")
            if t_id and t_id not in nodes_map:
                t_data = self._parse_json(row.get("target_data"))
                nodes_map[t_id] = GraphNode(
                    id=t_id, 
                    type_id=row.get("target_type_id", ""), 
                    data=t_data
                )
                object_ids_to_fetch.add(t_id)

            # Edge
            l_id = row.get("link_id")
            if l_id: 
                l_data = self._parse_json(row.get("link_data"))
                
                # Verify we have source and target IDs
                s_id = s_id or row.get("source_id")
                t_id = t_id or row.get("target_id")
                
                if s_id and t_id:
                    edge = GraphEdge(
                        id=l_id,
                        type_id=row.get("link_type_id", ""),
                        source_id=s_id,
                        target_id=t_id,
                        data=l_data
                    )
                    edges.append(edge)
        
        # Enrich with PostgreSQL data
        if object_ids_to_fetch:
            try:
                enriched_objects = self.object_repo.list_by_ids(session, list(object_ids_to_fetch))
                enrichment_map = {obj.id: obj for obj in enriched_objects}
                
                for node_id, node in nodes_map.items():
                    if node_id in enrichment_map:
                        node.details = enrichment_map[node_id]
            except Exception as e:
                logger.error(f"Failed to enrich objects from PostgreSQL: {e}")
                # Don't fail the whole query if enrichment fails, just return nodes without details
        
        return GraphResult(
            nodes=list(nodes_map.values()),
            edges=edges
        )
