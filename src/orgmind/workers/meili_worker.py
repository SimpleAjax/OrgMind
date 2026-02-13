"""
Meilisearch Index Worker - Event-driven full-text search synchronization worker.

This worker subscribes to domain events and maintains a real-time 
full-text search index in Meilisearch.
"""

import logging
from typing import Dict, Any

from orgmind.events import Event, EventType, EventBus
from orgmind.storage.search.meilisearch import MeiliSearchStore

logger = logging.getLogger(__name__)


class MeilisearchIndexWorker:
    """
    Background worker that syncs domain events to Meilisearch index.
    
    This worker:
    1. Subscribes to object events
    2. Flattens object data for efficient search
    3. Updates Meilisearch index
    """
    
    INDEX_NAME = "objects"
    
    def __init__(
        self,
        event_bus: EventBus,
        search_store: MeiliSearchStore,
    ):
        """
        Initialize the index worker.
        
        Args:
            event_bus: Event bus to subscribe to
            search_store: Meilisearch store adapter
        """
        self.event_bus = event_bus
        self.search_store = search_store
        self._running = False
    
    async def start(self) -> None:
        """Start the worker and subscribe to events."""
        self._running = True
        
        # Connect to Meilisearch
        await self.search_store.connect()
        
        # Ensure index exists
        await self.search_store.create_index(name=self.INDEX_NAME, primary_key="id")
        
        # Subscribe to object events
        await self.event_bus.subscribe("orgmind.object.*", self._handle_event)
        
        logger.info(f"Meilisearch Index Worker started (Index: {self.INDEX_NAME})")
    
    async def stop(self) -> None:
        """Stop the worker and disconnect."""
        self._running = False
        await self.event_bus.unsubscribe("orgmind.object.*")
        await self.search_store.close()
        logger.info("Meilisearch Index Worker stopped")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming domain event."""
        try:
            if event.event_type == EventType.OBJECT_CREATED or event.event_type == EventType.OBJECT_UPDATED:
                await self._handle_upsert(event)
            elif event.event_type == EventType.OBJECT_DELETED:
                await self._handle_delete(event)
        except Exception as e:
            logger.error(
                f"Failed to process event {event.event_id}: {e}",
                exc_info=True,
                extra={"event_id": str(event.event_id)}
            )

    def _flatten(self, data: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """
        Flatten dictionary for basic search indexing if needed.
        Meilisearch handles nested JSON well, but flattening can sometimes help 
        with specific field targeting if the depth is unknown.
        
        However, Meilisearch encourages keeping JSON structure. 
        We'll keep it simple and just passthrough the data, 
        maybe adding some metadata fields at top level.
        """
        return data

    async def _handle_upsert(self, event: Event) -> None:
        """Handle object creation/update."""
        payload = event.payload
        object_id = str(payload.get("object_id"))
        data = payload.get("data", {})
        
        # Construct document
        # We include system fields at top level for filtering
        document = {
            "id": object_id,
            "type_id": str(payload.get("object_type_id")),
            "tenant_id": str(event.tenant_id),
            # Flattened or nested data? Meilisearch supports nested.
            # We'll put data under 'data' key or merge at top level?
            # Merging at top level is usually better for "search everything"
            **data 
        }
        
        await self.search_store.index_documents(self.INDEX_NAME, [document])
        
        logger.info(
            f"Indexed object {object_id} in Meilisearch",
            extra={"object_id": object_id}
        )

    async def _handle_delete(self, event: Event) -> None:
        """Handle object deletion."""
        object_id = str(event.payload.get("object_id"))
        
        await self.search_store.delete_documents(self.INDEX_NAME, [object_id])
        
        logger.info(
            f"Deleted object {object_id} from Meilisearch",
            extra={"object_id": object_id}
        )
