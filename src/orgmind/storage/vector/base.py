from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class VectorPoint:
    id: str  # UUID or string ID
    vector: List[float]
    payload: Dict[str, Any]
    score: float = 0.0  # Search relevance score

class VectorStore(ABC):
    """Abstract interface for vector database operations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the vector engine."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the vector engine is reachable."""
        pass

    @abstractmethod
    async def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """
        Create a new collection if it doesn't exist.
        
        Args:
            name: Collection name
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Euclidean, Dot)
        """
        pass

    @abstractmethod
    async def upsert(self, collection: str, points: List[VectorPoint]) -> bool:
        """
        Insert or update vectors in the collection.
        """
        pass

    @abstractmethod
    async def search(
        self, 
        collection: str, 
        vector: List[float], 
        limit: int = 10, 
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> List[VectorPoint]:
        """
        Search for similar vectors.
        
        Args:
            collection: Collection name
            vector: Query vector
            limit: Max results to return
            filter: Metadata filter (engine-specific format for now, or unified dict)
            score_threshold: Minimum similarity score to return results
        """
        pass

    @abstractmethod
    async def delete(self, collection: str, point_ids: List[str]) -> bool:
        """Delete vectors by their IDs."""
        pass
