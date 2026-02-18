import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from orgmind.platform.config import settings
from orgmind.storage.vector.base import VectorPoint
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.platform.ai.embeddings import get_embedding_provider
from orgmind.agents.schemas import MemoryCreate, MemoryResponse, MemoryFilter

import structlog

logger = structlog.get_logger()

class MemoryStore:
    COLLECTION_NAME = "agent_memory"
    VECTOR_SIZE = 384  # Default for all-MiniLM-L6-v2, configurable via settings if needed

    def __init__(self):
        self.vector_store = QdrantVectorStore()
        self.embedding_service = get_embedding_provider()

    async def initialize(self):
        """Ensure the collection exists."""
        await self.vector_store.connect()
        # Initialize embedding service dimensions if possible
        if hasattr(self.embedding_service, "dimension"):
             # Update vector size to match actual provider
             self.VECTOR_SIZE = self.embedding_service.dimension
        
        # Create collection if not exists
        await self.vector_store.create_collection(
            name=self.COLLECTION_NAME,
            vector_size=self.VECTOR_SIZE,
            distance="Cosine"
        )

    async def add_memory(self, memory: MemoryCreate) -> MemoryResponse:
        """Add a memory to the store."""
        
        # 1. Generate Embedding
        vectors = await self.embedding_service.embed(memory.content)
        if not vectors:
            raise ValueError("Failed to generate embedding for memory content")
        vector = vectors[0]

        # 2. Prepare Payload
        memory_id = str(uuid.uuid4())
        timestamp = memory.created_at or datetime.now(timezone.utc)
        
        payload = {
            "content": memory.content,
            "role": memory.role,
            "agent_id": memory.agent_id,
            "user_id": memory.user_id,
            "conversation_id": memory.conversation_id,
            "type": memory.type,
            "created_at": timestamp.isoformat(),
            "access_list": memory.access_list
        }

        point = VectorPoint(
            id=memory_id,
            vector=vector,
            payload=payload
        )

        # 3. Upsert to Qdrant
        await self.vector_store.upsert(self.COLLECTION_NAME, [point])

        return MemoryResponse(
            id=memory_id,
            **memory.model_dump(exclude={"created_at"}),
            created_at=timestamp
        )

    async def search_memory(
        self, 
        query: str, 
        filter_params: Optional[MemoryFilter] = None, 
        limit: int = 5,
        score_threshold: float = 0.5 # Filter out low relevance
    ) -> List[MemoryResponse]:
        """
        Search for memories relevant to the query.
        Applies filters for security and context.
        """
        
        # 1. Generate Embedding
        vectors = await self.embedding_service.embed(query)
        if not vectors:
             return []
        vector = vectors

        # 2. Build Filter
        from qdrant_client.http import models

        must_conditions = []

        if filter_params:
            if filter_params.agent_id:
                must_conditions.append(models.FieldCondition(key="agent_id", match=models.MatchValue(value=filter_params.agent_id)))
            
            if filter_params.conversation_id:
                must_conditions.append(models.FieldCondition(key="conversation_id", match=models.MatchValue(value=filter_params.conversation_id)))
                
            if filter_params.type:
                must_conditions.append(models.FieldCondition(key="type", match=models.MatchValue(value=filter_params.type)))

            # Access Control: 
            # User must be owner OR have access via access_list (e.g. specialized roles)
            if filter_params.user_id:
                # Logic: (owner == user_id) OR (access_list CONTAINS ANY [user_id, *roles])
                access_values = [filter_params.user_id]
                if filter_params.roles:
                    access_values.extend(filter_params.roles)

                permission_filter = models.Filter(
                    should=[
                        models.FieldCondition(key="user_id", match=models.MatchValue(value=filter_params.user_id)),
                        models.FieldCondition(key="access_list", match=models.MatchAny(any=access_values))
                    ]
                )
                must_conditions.append(permission_filter)

        qdrant_filter = models.Filter(must=must_conditions) if must_conditions else None

        # 3. Search Qdrant
        points = await self.vector_store.search(
            collection=self.COLLECTION_NAME,
            vector=vector,
            limit=limit,
            filter=qdrant_filter,
            score_threshold=score_threshold
        )

        # 4. Convert to Response
        return [
            MemoryResponse(
                id=p.id,
                content=p.payload.get("content"),
                role=p.payload.get("role"),
                agent_id=p.payload.get("agent_id"),
                user_id=p.payload.get("user_id"),
                conversation_id=p.payload.get("conversation_id"),
                type=p.payload.get("type", "raw"),
                created_at=datetime.fromisoformat(p.payload.get("created_at")) if p.payload.get("created_at") else None,
                access_list=p.payload.get("access_list", []),
                score=p.score
            )
            for p in points
        ]

    async def delete_memory(self, memory_id: str):
        await self.vector_store.delete(self.COLLECTION_NAME, [memory_id])
