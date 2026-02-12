"""
Neo4j Index Worker - Event-driven graph synchronization worker.

This worker subscribes to domain events and maintains a real-time
graph index in Neo4j, enabling fast relationship queries.
"""

from typing import Dict, Any
import logging
import asyncio
import json

from orgmind.events import Event, EventType, EventBus
from orgmind.graph.neo4j_adapter import Neo4jAdapter


logger = logging.getLogger(__name__)


class Neo4jIndexWorker:
    """
    Background worker that syncs domain events to Neo4j graph.
    
    This worker:
    1. Subscribes to all domain events (orgmind.>)
    2. Translates events into Cypher queries
    3. Maintains graph state in sync with PostgreSQL
    4. Enables fast relationship traversal queries
    
    This worker flattens JSON data into Neo4j properties to enable
    efficient graph queries on specific attributes (e.g. role, level).
    
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        neo4j_adapter: Neo4jAdapter,
    ):
        """
        Initialize the index worker.
        
        Args:
            event_bus: Event bus to subscribe to
            neo4j_adapter: Neo4j adapter for graph operations
        """
        self.event_bus = event_bus
        self.neo4j = neo4j_adapter
        self._running = False
    
    async def start(self) -> None:
        """
        Start the worker and subscribe to events.
        """
        self._running = True
        
        # Connect to Neo4j
        self.neo4j.connect()
        
        # Create indexes for performance
        self.neo4j.create_indexes()
        
        # Subscribe to all domain events
        await self.event_bus.subscribe("orgmind.>", self._handle_event)
        
        logger.info("Neo4j Index Worker started")
    
    async def stop(self) -> None:
        """
        Stop the worker and disconnect.
        """
        self._running = False
        
        # Unsubscribe from events
        await self.event_bus.unsubscribe("orgmind.>")
        
        # Disconnect from Neo4j
        self.neo4j.disconnect()
        
        logger.info("Neo4j Index Worker stopped")
    
    async def _handle_event(self, event: Event) -> None:
        """
        Handle incoming domain event and sync to graph.
        
        Args:
            event: Domain event to process
        """
        logger.info(
            f"Neo4j worker received event: {event.event_type.value}",
            extra={
                "event_id": str(event.event_id),
                "event_type": event.event_type.value,
                "entity_id": str(event.entity_id),
            },
        )
    
        try:
            handler_map = {
                EventType.OBJECT_CREATED: self._handle_object_created,
                EventType.OBJECT_UPDATED: self._handle_object_updated,
                EventType.OBJECT_DELETED: self._handle_object_deleted,
                EventType.LINK_CREATED: self._handle_link_created,
                EventType.LINK_DELETED: self._handle_link_deleted,
            }
            
            handler = handler_map.get(event.event_type)
            if handler:
                await handler(event)
                logger.info(f"Successfully processed event {event.event_id}")
            else:
                logger.debug(f"No handler for event type: {event.event_type}")
                
        except Exception as e:
            logger.error(
                f"Failed to process event {event.event_id}: {e}",
                exc_info=True,
            )
            # Don't raise - we want to continue processing other events
    
    def _flatten_and_sanitize(self, data: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
        """
        Flatten nested dictionary and sanitize values for Neo4j.
        
        Converts nested dictionaries into flat keys (parent_child) and
        ensures lists are homogeneous for Neo4j storage.
        
        Args:
            data: Dictionary to flatten
            parent_key: Current key prefix for recursion
            sep: Separator for flattened keys
            
        Returns:
            Flattened and sanitized dictionary
        """
        items: list = []
        
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                # Recursively flatten nested dictionaries
                items.extend(self._flatten_and_sanitize(v, new_key, sep=sep).items())
            
            elif isinstance(v, list):
                # Neo4j arrays must be homogeneous.
                # Check for empty list, or if all elements are primitives AND of the exactly same type.
                # Note: type(True) is bool, type(1) is int. They are different.
                is_homogeneous_primitives = (
                    v and 
                    all(isinstance(x, (str, int, float, bool)) for x in v) and
                    all(type(x) is type(v[0]) for x in v[1:])
                )

                if is_homogeneous_primitives:
                    items.append((new_key, v))
                else:
                    # Mixed types or complex objects -> Serialize elements to strings
                    # For primitives: str(x) (e.g. 1 -> "1", True -> "True", "a" -> "a")
                    # For complex: json.dumps(x)
                    items.append((new_key, [
                        json.dumps(x) if isinstance(x, (dict, list)) else str(x) 
                        for x in v
                    ]))
            
            elif v is None:
                continue
            
            elif isinstance(v, (str, int, float, bool)):
                items.append((new_key, v))
            
            else:
                # Fallback for unknown types
                items.append((new_key, str(v)))
                
        return dict(items)

    async def _handle_object_created(self, event: Event) -> None:
        """
        Handle object.created event by creating a node in Neo4j.
        
        Args:
            event: Object created event
        """
        payload = event.payload
        object_id = payload.get("object_id")
        object_type_id = payload.get("object_type_id")
        data = payload.get("data", {})
        
        # Flatten data for property indexing
        flat_data = self._flatten_and_sanitize(data)
        
        # Create node with properties
        query = """
        MERGE (o:Object {id: $object_id})
        SET o += $props,
            o.type_id = $object_type_id,
            o.tenant_id = $tenant_id,
            o.updated_at = datetime(),
            o.created_at = coalesce(o.created_at, datetime())
        RETURN o
        """
        
        parameters = {
            "object_id": object_id,
            "object_type_id": object_type_id,
            "tenant_id": str(event.tenant_id),
            "props": flat_data,
        }
        
        self.neo4j.execute_write(query, parameters)
        
        logger.info(
            f"Created node for object {object_id}",
            extra={"object_id": object_id, "type_id": object_type_id},
        )
    
    async def _handle_object_updated(self, event: Event) -> None:
        """
        Handle object.updated event by updating node properties.
        
        Args:
            event: Object updated event
        """
        payload = event.payload
        object_id = payload.get("object_id")
        object_type_id = payload.get("object_type_id")
        data = payload.get("data", {})
        changed_fields = event.metadata.get("changed_fields", [])
        
        # Flatten data for property indexing
        flat_data = self._flatten_and_sanitize(data)
        
        # Update node properties
        # Using += to merge new properties. 
        # Note: This doesn't remove properties that were removed in the JSON.
        # For full sync involving removals, we'd need to clear data properties first.
        query = """
        MATCH (o:Object {id: $object_id})
        SET o += $props,
            o.type_id = $object_type_id,
            o.tenant_id = $tenant_id,
            o.updated_at = datetime()
        RETURN o
        """
        
        parameters = {
            "object_id": object_id,
            "object_type_id": object_type_id,
            "tenant_id": str(event.tenant_id),
            "props": flat_data,
        }
        
        self.neo4j.execute_write(query, parameters)
        
        logger.info(
            f"Updated node for object {object_id}",
            extra={
                "object_id": object_id,
                "type_id": object_type_id,
                "changed_fields": changed_fields,
            },
        )
    
    async def _handle_object_deleted(self, event: Event) -> None:
        """
        Handle object.deleted event by removing node from graph.
        
        Args:
            event: Object deleted event
        """
        payload = event.payload
        object_id = payload.get("object_id")
        
        # Delete node and all its relationships
        query = """
        MATCH (o:Object {id: $object_id})
        DETACH DELETE o
        """
        
        parameters = {"object_id": object_id}
        
        self.neo4j.execute_write(query, parameters)
        
        logger.info(
            f"Deleted node for object {object_id}",
            extra={"object_id": object_id},
        )
    
    async def _handle_link_created(self, event: Event) -> None:
        """
        Handle link.created event by creating a relationship in Neo4j.
        
        Args:
            event: Link created event
        """
        payload = event.payload
        link_id = payload.get("link_id")
        link_type_id = payload.get("link_type_id")
        from_object_id = payload.get("from_object_id")
        to_object_id = payload.get("to_object_id")
        data = payload.get("data", {})
        
        # Flatten data for relationship properties
        flat_data = self._flatten_and_sanitize(data)
        
        # Create relationship between nodes
        # Use dynamic relationship type based on link_type_id
        query = """
        MATCH (from:Object {id: $from_object_id})
        MATCH (to:Object {id: $to_object_id})
        MERGE (from)-[r:LINK {id: $link_id}]->(to)
        SET r += $props,
            r.type_id = $link_type_id,
            r.tenant_id = $tenant_id,
            r.updated_at = datetime(),
            r.created_at = coalesce(r.created_at, datetime())
        RETURN r
        """
        
        parameters = {
            "link_id": link_id,
            "link_type_id": link_type_id,
            "from_object_id": from_object_id,
            "to_object_id": to_object_id,
            "tenant_id": str(event.tenant_id),
            "props": flat_data,
        }
        
        self.neo4j.execute_write(query, parameters)
        
        logger.info(
            f"Created relationship for link {link_id}",
            extra={
                "link_id": link_id,
                "type_id": link_type_id,
                "from": from_object_id,
                "to": to_object_id,
            },
        )
    
    async def _handle_link_deleted(self, event: Event) -> None:
        """
        Handle link.deleted event by removing relationship from graph.
        
        Args:
            event: Link deleted event
        """
        payload = event.payload
        link_id = payload.get("link_id")
        
        # Delete relationship
        query = """
        MATCH ()-[r:LINK {id: $link_id}]->()
        DELETE r
        """
        
        parameters = {"link_id": link_id}
        
        self.neo4j.execute_write(query, parameters)
        
        logger.info(
            f"Deleted relationship for link {link_id}",
            extra={"link_id": link_id},
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get stats about the graph index.
        
        Returns:
            Dictionary with node and relationship counts
        """
        return {
            "nodes": self.neo4j.get_node_count(),
            "relationships": self.neo4j.get_relationship_count(),
            "healthy": self.neo4j.health_check(),
        }
