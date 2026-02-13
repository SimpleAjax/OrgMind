from typing import List, Dict, Any, Optional
import structlog
import httpx

from orgmind.platform.config import settings
from orgmind.storage.search.base import SearchStore, SearchResult, SearchIndex

logger = structlog.get_logger()

class MeiliSearchStore(SearchStore):
    """Meilisearch implementation of SearchStore using httpx for async."""

    def __init__(self):
        self._url = settings.MEILISEARCH_HOST
        self._api_key = settings.MEILISEARCH_API_KEY
        self.client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        if not self.client:
            self.client = httpx.AsyncClient(
                base_url=self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10.0
            )

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None
            
    async def _ensure_connected(self):
        if not self.client:
            await self.connect()

    async def health_check(self) -> bool:
        await self._ensure_connected()
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200 and resp.json().get("status") == "available"
        except Exception as e:
            logger.error("meilisearch_health_check_failed", error=str(e))
            return False

    async def create_index(self, name: str, primary_key: str = "id") -> bool:
        await self._ensure_connected()
        try:
            # Check if exists
            resp = await self.client.get(f"/indexes/{name}")
            if resp.status_code == 200:
                return True
                
            # Create
            payload = {"uid": name, "primaryKey": primary_key}
            resp = await self.client.post("/indexes", json=payload)
            resp.raise_for_status()
            logger.info("created_meilisearch_index", index=name)
            return True
        except Exception as e:
            logger.error("create_index_failed", error=str(e))
            raise

    async def index_documents(self, index: str, documents: List[Dict[str, Any]]) -> bool:
        await self._ensure_connected()
        if not documents:
            return True
        try:
            resp = await self.client.post(f"/indexes/{index}/documents", json=documents)
            resp.raise_for_status()
            task = resp.json()
            logger.debug("indexed_documents", index=index, count=len(documents), task_uid=task.get("taskUid"))
            return True
        except Exception as e:
            logger.error("index_documents_failed", error=str(e))
            raise

    async def search(
        self, 
        index: str, 
        query: str, 
        limit: int = 20, 
        filter: Optional[str] = None
    ) -> List[SearchResult]:
        await self._ensure_connected()
        try:
            payload = {
                "q": query,
                "limit": limit,
                "showRankingScore": True
            }
            if filter:
                payload["filter"] = filter
                
            resp = await self.client.post(f"/indexes/{index}/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            return [
                SearchResult(
                    id=str(hit.get("id", "")),
                    doc=hit,
                    score=hit.get("_rankingScore", 0.0)
                )
                for hit in data.get("hits", [])
            ]
        except Exception as e:
            logger.error("search_failed", error=str(e))
            raise

    async def delete_documents(self, index: str, doc_ids: List[str]) -> bool:
        await self._ensure_connected()
        try:
            resp = await self.client.post(f"/indexes/{index}/documents/delete-batch", json=doc_ids)
            resp.raise_for_status()
            task = resp.json()
            logger.debug("deleted_documents", index=index, count=len(doc_ids), task_uid=task.get("taskUid"))
            return True
        except Exception as e:
            logger.error("delete_documents_failed", error=str(e))
            raise
