"""
Unit tests for Neo4j Index Worker logic.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from orgmind.events import Event, EventType
from orgmind.graph.neo4j_index_worker import Neo4jIndexWorker
from orgmind.graph.neo4j_adapter import Neo4jAdapter

@pytest.fixture
def mock_adapter():
    return MagicMock(spec=Neo4jAdapter)

@pytest.fixture
def mock_bus():
    return AsyncMock()

@pytest.fixture
def worker(mock_bus, mock_adapter):
    return Neo4jIndexWorker(mock_bus, mock_adapter)

def test_flatten_and_sanitize_simple(worker):
    data = {"a": 1, "b": "test", "c": True}
    flat = worker._flatten_and_sanitize(data)
    assert flat == {"a": 1, "b": "test", "c": True}

def test_flatten_and_sanitize_nested(worker):
    data = {
        "user": {
            "name": "Alice",
            "address": {
                "city": "Wonderland",
                "zip": 12345
            }
        }
    }
    flat = worker._flatten_and_sanitize(data)
    assert flat["user_name"] == "Alice"
    assert flat["user_address_city"] == "Wonderland"
    assert flat["user_address_zip"] == 12345

def test_flatten_and_sanitize_lists(worker):
    data = {
        "tags": ["a", "b", "c"], # Homogeneous string list
        "scores": [1, 2, 3], # Homogeneous int list
        "mixed": [1, "two", 3.0], # Mixed -> serialize
        "dicts": [{"a": 1}, {"b": 2}] # Complex -> serialize
    }
    flat = worker._flatten_and_sanitize(data)
    assert flat["tags"] == ["a", "b", "c"]
    assert flat["scores"] == [1, 2, 3]
    
    # Mixed list should be serialized to strings
    assert flat["mixed"] == ["1", "two", "3.0"]
    
    # Dict list should be serialized to JSON strings
    assert len(flat["dicts"]) == 2
    assert isinstance(flat["dicts"][0], str)
    assert json.loads(flat["dicts"][0]) == {"a": 1}

@pytest.mark.asyncio
async def test_handle_object_created(worker, mock_adapter):
    obj_id = uuid4()
    type_id = uuid4()
    tenant_id = uuid4()
    
    event = Event(
        event_id=uuid4(),
        event_type=EventType.OBJECT_CREATED,
        entity_id=obj_id,
        entity_type="object",
        tenant_id=tenant_id,
        payload={
            "object_id": str(obj_id),
            "object_type_id": str(type_id),
            "data": {"name": "Test Object", "meta": {"version": 1}}
        }
    )
    
    await worker._handle_object_created(event)
    
    mock_adapter.execute_write.assert_called_once()
    args, kwargs = mock_adapter.execute_write.call_args
    query = args[0]
    params = args[1]
    
    assert "MERGE (o:Object {id: $object_id})" in query
    assert params["object_id"] == str(obj_id)
    assert params["object_type_id"] == str(type_id)
    assert params["tenant_id"] == str(tenant_id)
    assert params["props"]["name"] == "Test Object"
    assert params["props"]["meta_version"] == 1

@pytest.mark.asyncio
async def test_handle_object_updated(worker, mock_adapter):
    obj_id = uuid4()
    type_id = uuid4()
    tenant_id = uuid4()
    
    event = Event(
        event_id=uuid4(),
        event_type=EventType.OBJECT_UPDATED,
        entity_id=obj_id,
        entity_type="object",
        tenant_id=tenant_id,
        payload={
            "object_id": str(obj_id),
            "object_type_id": str(type_id),
            "data": {"status": "active"}
        },
        metadata={"changed_fields": ["status"]}
    )
    
    await worker._handle_object_updated(event)
    
    mock_adapter.execute_write.assert_called_once()
    args, _ = mock_adapter.execute_write.call_args
    query = args[0]
    params = args[1]
    
    assert "MATCH (o:Object {id: $object_id})" in query
    assert "SET o += $props" in query
    assert params["props"]["status"] == "active"

@pytest.mark.asyncio
async def test_handle_object_deleted(worker, mock_adapter):
    obj_id = uuid4()
    
    event = Event(
        event_id=uuid4(),
        event_type=EventType.OBJECT_DELETED,
        entity_id=obj_id,
        entity_type="object",
        tenant_id=uuid4(),
        payload={
            "object_id": str(obj_id)
        }
    )
    
    await worker._handle_object_deleted(event)
    
    mock_adapter.execute_write.assert_called_once()
    args, _ = mock_adapter.execute_write.call_args
    query = args[0]
    params = args[1]
    
    assert "DETACH DELETE o" in query
    assert params["object_id"] == str(obj_id)
