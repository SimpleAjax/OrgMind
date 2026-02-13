"""
Unit tests for Meilisearch synchronization.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

from orgmind.events import NatsEventBus, Event, EventType
from orgmind.storage.search.meilisearch import MeiliSearchStore
from orgmind.workers.meili_worker import MeilisearchIndexWorker

@pytest.fixture
async def mock_event_bus():
    """Create a mock event bus."""
    bus = AsyncMock(spec=NatsEventBus)
    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()
    return bus

@pytest.fixture
async def mock_search_store():
    """Create a mock search store."""
    store = AsyncMock(spec=MeiliSearchStore)
    store.connect = AsyncMock()
    store.create_index = AsyncMock()
    store.index_documents = AsyncMock()
    store.delete_documents = AsyncMock()
    store.close = AsyncMock()
    return store

@pytest.mark.asyncio
async def test_meili_worker_lifecycle(mock_event_bus, mock_search_store):
    """Test worker start/stop."""
    worker = MeilisearchIndexWorker(mock_event_bus, mock_search_store)
    
    await worker.start()
    
    mock_search_store.connect.assert_called_once()
    mock_search_store.create_index.assert_called_once()
    mock_event_bus.subscribe.assert_called_once()
    
    await worker.stop()
    
    mock_event_bus.unsubscribe.assert_called_once()
    mock_search_store.close.assert_called_once()

@pytest.mark.asyncio
async def test_object_created_indexes_document(mock_event_bus, mock_search_store):
    """Test object.created event handling."""
    worker = MeilisearchIndexWorker(mock_event_bus, mock_search_store)
    
    # Simulate event
    event = MagicMock(spec=Event)
    event.event_type = EventType.OBJECT_CREATED
    event.tenant_id = uuid4()
    event.event_id = uuid4()
    object_id = uuid4()
    type_id = uuid4()
    
    event.payload = {
        "object_id": str(object_id),
        "object_type_id": str(type_id),
        "data": {"name": "Searchable Item", "status": "active"}
    }
    
    # Process event
    await worker._handle_event(event)
    
    # Verify index called
    mock_search_store.index_documents.assert_called_once()
    index, docs = mock_search_store.index_documents.call_args[0]
    assert index == "objects"
    assert len(docs) == 1
    doc = docs[0]
    assert doc["id"] == str(object_id)
    assert doc["type_id"] == str(type_id)
    assert doc["name"] == "Searchable Item"
    assert doc["status"] == "active"

@pytest.mark.asyncio
async def test_object_deleted_removes_document(mock_event_bus, mock_search_store):
    """Test object.deleted event handling."""
    worker = MeilisearchIndexWorker(mock_event_bus, mock_search_store)
    
    # Simulate event
    event = MagicMock(spec=Event)
    event.event_type = EventType.OBJECT_DELETED
    event.event_id = uuid4()
    object_id = uuid4()
    
    event.payload = {
        "object_id": str(object_id)
    }
    
    # Process event
    await worker._handle_event(event)
    
    # Verify delete called
    mock_search_store.delete_documents.assert_called_once()
    index, ids = mock_search_store.delete_documents.call_args[0]
    assert index == "objects"
    assert ids == [str(object_id)]
