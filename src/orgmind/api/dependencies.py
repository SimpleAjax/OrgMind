from typing import Annotated, Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from orgmind.api.database import get_db, get_postgres_adapter, close_postgres_adapter
from orgmind.api.dependencies_auth import get_current_user, require_current_user, require_permission
from orgmind.events.nats_bus import NatsEventBus
from orgmind.events.publisher import EventPublisher
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.domain_event_repository import DomainEventRepository
from orgmind.engine.ontology_service import OntologyService
from orgmind.platform.config import settings

# New imports for Week 5
from orgmind.storage.vector.base import VectorStore
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.storage.search.base import SearchStore
from orgmind.storage.search.meilisearch import MeiliSearchStore
from orgmind.platform.ai.embeddings import EmbeddingProvider, get_embedding_provider as _get_embedding_provider_factory

# Singletons
_nats_bus: NatsEventBus | None = None
_vector_store: VectorStore | None = None
_search_store: SearchStore | None = None
_embedding_provider: EmbeddingProvider | None = None


def get_event_bus() -> NatsEventBus:
    global _nats_bus
    if not _nats_bus:
        _nats_bus = NatsEventBus(
            nats_url=settings.NATS_URL,
            max_reconnect_attempts=settings.NATS_MAX_RECONNECT_ATTEMPTS
        )
    return _nats_bus

def get_vector_store() -> VectorStore:
    global _vector_store
    if not _vector_store:
        _vector_store = QdrantVectorStore()
    return _vector_store

def get_search_store() -> SearchStore:
    global _search_store
    if not _search_store:
        _search_store = MeiliSearchStore()
    return _search_store

def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if not _embedding_provider:
        _embedding_provider = _get_embedding_provider_factory()
    return _embedding_provider

async def init_resources() -> None:
    """Initialize all resources (DB, NATS, Vector, Search)."""
    adapter = get_postgres_adapter()
    adapter.connect()
    
    bus = get_event_bus()
    await bus.connect()
    
    # Initialize search/vector stores
    # We use fire-and-forget or await depending on startup requirements
    # Ideally async connect
    vec = get_vector_store()
    await vec.connect()
    
    search = get_search_store()
    await search.connect()

async def close_resources() -> None:
    """Close all resources."""
    global _nats_bus, _vector_store, _search_store
    
    close_postgres_adapter()
        
    if _nats_bus:
        await _nats_bus.disconnect()
        _nats_bus = None
        
    if _vector_store:
        await _vector_store.close()
        _vector_store = None
        
    if _search_store:
        await _search_store.close()
        _search_store = None


def get_event_publisher() -> EventPublisher:
    bus = get_event_bus()
    return EventPublisher(bus)

def get_ontology_service(
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> OntologyService:
    return OntologyService(
        object_repo=ObjectRepository(),
        link_repo=LinkRepository(),
        event_repo=DomainEventRepository(),
        event_publisher=publisher,
    )
