"""
Integration tests for Qdrant synchronization.
"""

import pytest
import asyncio
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

from orgmind.storage.models import ObjectModel, ObjectTypeModel
from orgmind.events import NatsEventBus
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.workers.qdrant_worker import QdrantIndexWorker
from orgmind.platform.ai.embeddings import EmbeddingProvider

@pytest.fixture
async def mock_event_bus():
    """Create a mock event bus."""
    bus = AsyncMock(spec=NatsEventBus)
    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()
    return bus

@pytest.fixture
async def mock_vector_store():
    """Create a mock vector store."""
    store = AsyncMock(spec=QdrantVectorStore)
    store.connect = AsyncMock()
    store.create_collection = AsyncMock()
    store.upsert = AsyncMock()
    store.delete = AsyncMock()
    store.close = AsyncMock()
    return store

@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    provider = MagicMock(spec=EmbeddingProvider)
    provider.dimension = 384
    # Mock embed to return a vector of correct dimension
    provider.embed = AsyncMock(return_value=[0.1] * 384)
    return provider

@pytest.mark.asyncio
async def test_qdrant_worker_lifecycle(mock_event_bus, mock_vector_store, mock_embedding_provider):
    """Test worker start/stop."""
    worker = QdrantIndexWorker(mock_event_bus, mock_vector_store)
    # Inject mock provider
    worker.embedding_provider = mock_embedding_provider
    
    await worker.start()
    
    mock_vector_store.connect.assert_called_once()
    mock_vector_store.create_collection.assert_called_once()
    mock_event_bus.subscribe.assert_called_once()
    
    await worker.stop()
    
    mock_event_bus.unsubscribe.assert_called_once()
    mock_vector_store.close.assert_called_once()

@pytest.mark.asyncio
async def test_object_created_upserts_vector(mock_event_bus, mock_vector_store, mock_embedding_provider):
    """Test object.created event handling."""
    worker = QdrantIndexWorker(mock_event_bus, mock_vector_store)
    worker.embedding_provider = mock_embedding_provider
    
    # Simulate event
    event = MagicMock()
    event.event_type = "object.created"
    event.tenant_id = uuid4()
    event.event_id = uuid4()
    object_id = uuid4()
    type_id = uuid4()
    
    event.payload = {
        "object_id": str(object_id),
        "object_type_id": str(type_id),
        "data": {"name": "Test Object", "description": "Analyzing things"}
    }
    
    # Process event
    await worker._handle_event(event)
    
    # Verify embedding called
    mock_embedding_provider.embed.assert_called_once()
    
    # Verify upsert called
    mock_vector_store.upsert.assert_called_once()
    collection, points = mock_vector_store.upsert.call_args[0]
    assert collection == "objects"
    assert len(points) == 1
    assert points[0].id == str(object_id)
    assert points[0].payload["type_id"] == str(type_id)

@pytest.mark.asyncio
async def test_object_deleted_removes_vector(mock_event_bus, mock_vector_store, mock_embedding_provider):
    """Test object.deleted event handling."""
    worker = QdrantIndexWorker(mock_event_bus, mock_vector_store)
    worker.embedding_provider = mock_embedding_provider
    
    # Simulate event
    event = MagicMock()
    event.event_type = "object.deleted"
    event.event_id = uuid4()
    object_id = uuid4()
    
    event.payload = {
        "object_id": str(object_id)
    }
    
    # Process event
    await worker._handle_event(event)
    
    # Verify delete called
    mock_vector_store.delete.assert_called_once()
    collection, ids = mock_vector_store.delete.call_args[0]
    assert collection == "objects"
    assert ids == [str(object_id)]
