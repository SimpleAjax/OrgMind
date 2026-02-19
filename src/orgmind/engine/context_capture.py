import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.graph.neo4j_adapter import Neo4jAdapter
from orgmind.storage.models import ObjectModel
from orgmind.storage.models_traces import ContextSnapshotModel

logger = logging.getLogger(__name__)

class ContextSnapshotService:
    """
    Service to capture the state of the world (entities and graph context)
    at a specific point in time to support decision traceability.
    """
    
    def __init__(self, postgres_adapter: PostgresAdapter, neo4j_adapter: Neo4jAdapter):
        self.postgres = postgres_adapter
        self.neo4j = neo4j_adapter
        
    def capture_snapshot(self, entity_ids: List[str], depth: int = 1) -> str:
        """
        Captures a snapshot of the specified entities and their graph neighborhood.
        
        Args:
            entity_ids: List of entity IDs to focus the snapshot on.
            depth: Graph depth for neighborhood capture (default 1).
            
        Returns:
            The ID of the created snapshot.
        """
        snapshot_id = str(uuid.uuid4())
        
        try:
            # 1. Fetch Entity States (Properties) from Postgres
            # We fetch current state. In a real event-sourced system we might need time-travel,
            # but for now we assume "now" is close enough to when the decision happened.
            entity_states = self._fetch_entity_states(entity_ids)
            
            # 2. Fetch Graph Neighborhood from Neo4j
            graph_context = self._fetch_graph_context(entity_ids, depth)
            
            # 3. Store Snapshot
            with self.postgres.get_session() as session:
                snapshot = ContextSnapshotModel(
                    id=snapshot_id,
                    entity_states=entity_states,
                    graph_neighborhood=graph_context,
                    timestamp=datetime.utcnow()
                )
                session.add(snapshot)
                session.commit()
                
            logger.info(f"Captured context snapshot {snapshot_id} for entities {entity_ids}")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to capture context snapshot: {e}")
            # We might want to return None or raise, but for traceability being "best effort" 
            # might be acceptable depending on strictness. For now raise.
            raise

    def _fetch_entity_states(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Fetch current properties of entities from relational store."""
        if not entity_ids:
            return {}
            
        with self.postgres.get_session() as session:
            # We could optimize this query
            objects = session.query(ObjectModel).filter(ObjectModel.id.in_(entity_ids)).all()
            return {
                obj.id: {
                    "type": obj.type_id,
                    "data": obj.data,
                    "status": obj.status,
                    "version": obj.version
                }
                for obj in objects
            }

    def _fetch_graph_context(self, entity_ids: List[str], depth: int) -> Dict[str, Any]:
        """Fetch topology around entities."""
        if not entity_ids:
            return {"nodes": [], "relationships": []}
            
        # Cypher query to get neighborhood
        # Using a simple variable length path query
        query = """
        MATCH (start:Object)
        WHERE start.id IN $entity_ids
        CALL {
            WITH start
            MATCH (start)-[r*0..1]-(neighbor)
            RETURN neighbor, r
        }
        RETURN 
            collect(DISTINCT neighbor) as nodes, 
            collect(DISTINCT r) as rels
        """
        
        try:
            results = self.neo4j.execute_read(query, {"entity_ids": entity_ids})
            if not results:
                return {"nodes": [], "relationships": []}
            
            record = results[0]
            nodes = [dict(n) for n in record.get("nodes", [])]
            rels = [
                {
                    "id": r.element_id if hasattr(r, 'element_id') else r.id,
                    "start": r.start_node.element_id if hasattr(r.start_node, 'element_id') else r.start_node.id, 
                    # Neo4j python driver structure might vary, strictly 'start' and 'end' nodes 
                    # are objects, we need their properties or IDs.
                    # Usually better to return properties.
                    "type": r.type,
                    "properties": dict(r)
                } 
                for r in record.get("rels", []) 
                if isinstance(r, list) == False # Verify it's not a list of lists
            ]
            
            # Helper to clean up node formatting if needed
            cleaned_nodes = []
            for n in nodes:
                # Neo4j Node object to dict usually works, but let's be safe
                cleaned_nodes.append(dict(n))

            return {
                "nodes": cleaned_nodes,
                "relationships": rels # This might need more parsing depending on driver version
            }
            
        except Exception as e:
            logger.error(f"Error fetching graph context: {e}")
            return {"error": str(e)}
