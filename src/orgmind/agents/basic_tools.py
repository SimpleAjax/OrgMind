from typing import Optional, List, Dict, Any, Type
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import asyncio

from orgmind.agents.tools import Tool, tool_registry
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.api.dependencies import get_vector_store, get_embedding_provider
from orgmind.storage.vector.base import VectorStore
from orgmind.platform.config import settings

class QueryObjectsParams(BaseModel):
    query: Optional[str] = Field(None, description="Search query string")
    type_id: Optional[str] = Field(None, description="Filter by Object Type ID")
    limit: int = Field(5, description="Number of results to return")

class QueryObjectsTool(Tool):
    name = "query_objects"
    description = "Search for objects in the ontology by type or keyword."
    parameters = QueryObjectsParams

    async def run(self, session: Session, query: Optional[str] = None, type_id: Optional[str] = None, limit: int = 5, **kwargs) -> Any:
        repo = ObjectRepository()
        if type_id:
            # If type_id is provided, use repo list
            results = repo.list_by_type(session, type_id, limit=limit)
        else:
             # Basic list if no type
             results = repo.list(session, limit=limit)
        
        # If query string provided, naive in-memory filter
        if query and query.strip():
            q_lower = query.lower()
            filtered = []
            for obj in results:
                if q_lower in str(obj.data).lower() or q_lower in obj.id.lower():
                    filtered.append(obj)
            results = filtered[:limit]

        return [
            {"id": obj.id, "type_id": obj.type_id, "data": obj.data}
            for obj in results
        ]

class SemanticSearchParams(BaseModel):
    query: str = Field(..., description="The semantic search query")
    limit: int = Field(5, description="Number of results to return")
    threshold: float = Field(0.7, description="Similarity threshold")

class SemanticSearchTool(Tool):
    name = "semantic_search"
    description = "Search for objects using semantic similarity (meaning)."
    parameters = SemanticSearchParams

    async def run(self, query: str, limit: int = 5, threshold: float = 0.7, **kwargs) -> Any:
        try:
            vector_store = get_vector_store()
            embedding_provider = get_embedding_provider()
            
            # Embed the query
            embeddings = await embedding_provider.embed_texts([query])
            if not embeddings:
                return []
            vector = embeddings[0]
            
            # Search
            results = await vector_store.search(
                collection="objects", # Assuming 'objects' is the collection name
                vector=vector,
                limit=limit,
                score_threshold=threshold
            )
            
            return [
                {
                    "id": point.id, 
                    "score": point.score, 
                    "payload": point.payload
                }
                for point in results
            ]
        except Exception as e:
            return f"Error executing semantic search: {str(e)}"

# Register tools
tool_registry.register(QueryObjectsTool())
tool_registry.register(SemanticSearchTool())
