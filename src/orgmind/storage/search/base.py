"""
Search Storage modules for OrgMind (Full-Text Search).
"""
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SearchResult:
    id: str
    doc: Dict[str, Any]
    score: float = 0.0

@dataclass
class SearchIndex:
    name: str
    primary_key: str = "id"

class SearchStore(ABC):
    """Abstract interface for full-text search engine operations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if reachable."""
        pass

    @abstractmethod
    async def create_index(self, name: str, primary_key: str = "id") -> bool:
        """Create a new index."""
        pass

    @abstractmethod
    async def index_documents(self, index: str, documents: List[Dict[str, Any]]) -> bool:
        """Add or update documents in the index."""
        pass

    @abstractmethod
    async def search(
        self, 
        index: str, 
        query: str, 
        limit: int = 20, 
        filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search documents.
        
        Args:
            index: Index name
            query: Text query string
            limit: Max results
            filter: Filter expression (engine-specific usually, plan for unified later)
        """
        pass

    @abstractmethod
    async def delete_documents(self, index: str, doc_ids: List[str]) -> bool:
        """Delete documents by ID."""
        pass
