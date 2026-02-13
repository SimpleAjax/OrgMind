import structlog
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from orgmind.platform.config import settings
from orgmind.storage.vector.base import VectorStore, VectorPoint

logger = structlog.get_logger()

class QdrantVectorStore(VectorStore):
    """Qdrant implementation of VectorStore."""

    def __init__(self):
        self.client: Optional[AsyncQdrantClient] = None
        self._host = settings.QDRANT_HOST
        self._port = settings.QDRANT_PORT
        self._grpc_port = settings.QDRANT_GRPC_PORT

    async def connect(self) -> None:
        if not self.client:
            logger.info("connecting_to_qdrant", host=self._host, port=self._port)
            self.client = AsyncQdrantClient(
                host=self._host,
                port=self._port,
                grpc_port=self._grpc_port,
                prefer_grpc=True
            )

    async def close(self) -> None:
        if self.client:
            # Qdrant client doesn't explicitly require close for HTTP/gRPC in some versions,
            # but good practice for cleanup if needed.
            # Current async client might not have a close method depending on version, 
            # checking common patterns.
            # client.close() is synchronous usually if wrapper around httpx?
            # Creating a new client per request or keeping singleton is standard.
            # We'll assume singleton lifecycle managed by dependency injection.
            await self.client.close()
            self.client = None

    async def health_check(self) -> bool:
        if not self.client:
            await self.connect()
        try:
            # Simple check - list collections
            await self.client.get_collections()
            return True
        except Exception as e:
            logger.error("qdrant_health_check_failed", error=str(e))
            return False

    async def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        if not self.client:
            await self.connect()

        try:
            # Check if exists first
            collections = await self.client.get_collections()
            exists = any(c.name == name for c in collections.collections)
            
            if exists:
                logger.info("collection_already_exists", name=name)
                return True

            distance_map = {
                "Cosine": models.Distance.COSINE,
                "Euclidean": models.Distance.EUCLID,
                "Dot": models.Distance.DOT,
            }

            await self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance, models.Distance.COSINE)
                )
            )
            logger.info("created_collection", name=name)
            return True
        except Exception as e:
            logger.error("create_collection_failed", error=str(e))
            raise

    async def upsert(self, collection: str, points: List[VectorPoint]) -> bool:
        if not self.client:
            await self.connect()
            
        if not points:
            return True

        qdrant_points = [
            models.PointStruct(
                id=p.id,
                vector=p.vector,  # type: ignore # qdrant expects list of floats
                payload=p.payload
            )
            for p in points
        ]

        try:
            # upsert is async in the client
            await self.client.upsert(
                collection_name=collection,
                points=qdrant_points
            )
            return True
        except Exception as e:
            logger.error("upsert_failed", error=str(e))
            raise

    async def search(
        self, 
        collection: str, 
        vector: List[float], 
        limit: int = 10, 
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> List[VectorPoint]:
        if not self.client:
            await self.connect()

        try:
            # Transform generic filter to Qdrant Filter if provided
            # NOTE: For now, assuming raw Qdrant filter structure if passed
            # TODO: Implement generic -> Qdrant filter converter in Week 6
            query_filter = None
            if filter:
                 # Start with simple assumption: if it's already a models.Filter, use it
                 # If it's a dict, try to cast (risky without converter)
                 # For now, we will assume NO filter or valid Qdrant filter passed as dict
                 # We will implement the proper converter later.
                 query_filter = models.Filter(**filter) if filter else None

            # Qdrant client 1.10+ uses query_points instead of search
            results = await self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold
            )
            
            # query_points returns QueryResponse object in recent versions, which has 'points' attribute
            # check if results is a list or object
            points_list = results.points if hasattr(results, 'points') else results

            return [
                VectorPoint(
                    id=str(res.id),
                    vector=res.vector if res.vector else [], # type: ignore
                    payload=res.payload if res.payload else {},
                    score=res.score
                )
                for res in points_list
            ]
        except Exception as e:
            logger.error("search_failed", error=str(e))
            raise

    async def delete(self, collection: str, point_ids: List[str]) -> bool:
        if not self.client:
            await self.connect()
            
        try:
            await self.client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(
                    points=point_ids
                )
            )
            return True
        except Exception as e:
            logger.error("delete_failed", error=str(e))
            raise
