"""
Qdrant Index Worker - Event-driven vector synchronization worker.

This worker subscribes to domain events, generates embeddings for objects,
and maintains a real-time vector index in Qdrant.
"""

import json
import logging
from typing import Dict, Any, List
from uuid import UUID

from orgmind.events import Event, EventType, EventBus
from orgmind.storage.vector.base import VectorPoint
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.platform.ai.embeddings import get_embedding_provider, EmbeddingProvider

logger = logging.getLogger(__name__)


class QdrantIndexWorker:
    """
    Background worker that syncs domain events to Qdrant vector store.
    
    This worker:
    1. Subscribes to object events (created/updated/deleted)
    2. Generates embeddings for object content
    3. Updates Qdrant vector index
    """
    
    COLLECTION_NAME = "objects"
    
    def __init__(
        self,
        event_bus: EventBus,
        vector_store: QdrantVectorStore,
    ):
        """
        Initialize the index worker.
        
        Args:
            event_bus: Event bus to subscribe to
            vector_store: Qdrant vector store adapter
        """
        self.event_bus = event_bus
        self.vector_store = vector_store
        self.embedding_provider: EmbeddingProvider = get_embedding_provider()
        self._running = False
    
    async def start(self) -> None:
        """Start the worker and subscribe to events."""
        self._running = True
        
        # Connect to Qdrant
        await self.vector_store.connect()
        
        # Ensure collection exists
        # We use the dimension from the configured embedding provider
        dimension = self.embedding_provider.dimension
        await self.vector_store.create_collection(
            name=self.COLLECTION_NAME,
            vector_size=dimension,
            distance="Cosine"
        )
        
        # Subscribe to object events
        await self.event_bus.subscribe("orgmind.object.*", self._handle_event)
        
        logger.info(f"Qdrant Index Worker started (Collection: {self.COLLECTION_NAME}, Dim: {dimension})")
    
    async def stop(self) -> None:
        """Stop the worker and disconnect."""
        self._running = False
        await self.event_bus.unsubscribe("orgmind.object.*")
        await self.vector_store.close()
        logger.info("Qdrant Index Worker stopped")
    
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

    def _serialize_for_embedding(self, data: Dict[str, Any]) -> str:
        """
        Serialize object data to text for embedding.
        
        For now, we dump the JSON. In the future, this should be template-based
        or field-specific (e.g. only embedding 'summary', 'description', 'content').
        """
        # Improved serialization: filter out None, sort keys for stability
        return json.dumps(data, sort_keys=True, default=str)

    async def _handle_upsert(self, event: Event) -> None:
        """Handle object creation/update."""
        payload = event.payload
        object_id = str(payload.get("object_id"))
        data = payload.get("data", {})
        
        # 1. Generate text representation
        text_content = self._serialize_for_embedding(data)
        
        if not text_content:
            logger.warning(f"Empty content for object {object_id}, skipping embedding")
            return

        # 2. Generate embedding
        vector = await self.embedding_provider.embed(text_content)
        
        # 3. Create VectorPoint
        # We store metadata in payload for filtering
        point_payload = {
            "object_id": object_id,
            "type_id": str(payload.get("object_type_id")),
            "tenant_id": str(event.tenant_id),
            "content": text_content[:1000] # Store snippet for debug/context
        }
        
        point = VectorPoint(
            id=object_id,
            vector=vector,
            payload=point_payload
        )
        
        # 4. Upsert to Qdrant
        await self.vector_store.upsert(self.COLLECTION_NAME, [point])
        
        logger.info(
            f"Indexed object {object_id} in Qdrant",
            extra={"object_id": object_id}
        )

    async def _handle_delete(self, event: Event) -> None:
        """Handle object deletion."""
        object_id = str(event.payload.get("object_id"))
        
        await self.vector_store.delete(self.COLLECTION_NAME, [object_id])
        
        logger.info(
            f"Deleted object {object_id} from Qdrant",
            extra={"object_id": object_id}
        )
