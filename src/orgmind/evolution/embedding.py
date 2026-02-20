import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from qdrant_client.http import models

from orgmind.storage.vector.qdrant import QdrantVectorStore, VectorPoint
from orgmind.storage.models_traces import DecisionTraceModel, ContextSnapshotModel
from orgmind.storage.postgres_adapter import PostgresAdapter

logger = logging.getLogger(__name__)

class DecisionEmbeddingService:
    """
    Service to generate embeddings for decision context and store them in Qdrant
    for similarity search.
    """
    
    COLLECTION_NAME = "decision_traces"
    VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small
    
    def __init__(self, vector_store: QdrantVectorStore, postgres_adapter: PostgresAdapter, embedding_provider=None):
        self.vector_store = vector_store
        self.postgres = postgres_adapter
        # TODO: Inject real embedding provider (OpenAI or Local)
        self.embedding_provider = embedding_provider

    async def initialize(self) -> bool:
        """Ensures the Qdrant collection exists."""
        return await self.vector_store.create_collection(
            name=self.COLLECTION_NAME,
            vector_size=self.VECTOR_SIZE,
            distance="Cosine"
        )

    async def embed_decision(self, trace_id: str) -> bool:
        """
        Generates an embedding for a specific decision trace and stores it.
        The embedding represents the "Context" + "Action" to allow finding similar situations.
        """
        # 1. Fetch trace and snapshot
        trace, snapshot = self._get_trace_data(trace_id)
        if not trace:
            logger.error(f"Trace {trace_id} not found")
            return False
            
        # 2. Textual representation of the decision context
        # e.g. "User Bob decided to 'assign_task' doing {priority: high} when context was {day: Friday, project_status: delayed}"
        text_representation = self._generate_context_text(trace, snapshot)
        
        # 3. Generate Embedding
        if self.embedding_provider:
             # TODO: specific call to provider
             vector = await self.embedding_provider.embed_text(text_representation)
        else:
             # Mock for now if no provider
             logger.warning("No embedding provider, using random vector")
             import random
             vector = [random.random() for _ in range(self.VECTOR_SIZE)]

        # 4. Store in Qdrant
        point = VectorPoint(
            id=trace_id,
            vector=vector,
            payload={
                "trace_id": trace.id,
                "action_type": trace.action_type,
                "status": trace.status,
                "user_id": trace.user_id,
                "timestamp": trace.timestamp.isoformat(),
                "text_content": text_representation,
                 # Store key context variables for filtering?
                 # "project_id": ...
            }
        )
        
        return await self.vector_store.upsert(self.COLLECTION_NAME, [point])

    def _get_trace_data(self, trace_id: str):
        with self.postgres.get_session() as session:
            trace = session.get(DecisionTraceModel, trace_id)
            snapshot = None
            if trace and trace.snapshot_id:
                snapshot = session.get(ContextSnapshotModel, trace.snapshot_id)
            return trace, snapshot

    def _generate_context_text(self, trace: DecisionTraceModel, snapshot: Optional[ContextSnapshotModel]) -> str:
        """
        Constructs a semantic string describing the decision situation.
        """
        parts = [
            f"Action: {trace.action_type}",
            f"Status: {trace.status}",
        ]
        
        if trace.input_payload:
            parts.append(f"Input: {trace.input_payload}")
            
        if snapshot:
            # Flatten context snapshot relevant parts
            # This logic needs to be smart about what to include to avoid huge texts
            parts.append(f"Context Entities: {list(snapshot.entity_states.keys())}")
            # Add specific state values if configured
            
        return "\n".join(parts)

    async def search_similar(
        self, 
        current_context_text: str, 
        limit: int = 5,
        msg_filter: Optional[Dict] = None
    ) -> List[Any]:
        """
        Finds past decisions with similar context.
        """
        if self.embedding_provider:
             vector = await self.embedding_provider.embed_text(current_context_text)
        else:
             import random
             vector = [random.random() for _ in range(self.VECTOR_SIZE)]
             
        points = await self.vector_store.search(
            collection=self.COLLECTION_NAME,
            vector=vector,
            limit=limit,
            filter=msg_filter
        )
        
        return points
