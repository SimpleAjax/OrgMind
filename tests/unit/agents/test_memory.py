import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from orgmind.agents.memory import MemoryStore
from orgmind.agents.schemas import MemoryCreate, MemoryFilter
from orgmind.storage.vector.base import VectorPoint

@pytest.fixture
def mock_qdrant():
    with patch("orgmind.agents.memory.QdrantVectorStore") as mock:
        instance = mock.return_value
        instance.connect = AsyncMock()
        instance.create_collection = AsyncMock()
        instance.upsert = AsyncMock()
        instance.search = AsyncMock()
        instance.delete = AsyncMock()
        yield instance

@pytest.fixture
def mock_embedding_provider():
    with patch("orgmind.agents.memory.get_embedding_provider") as mock:
        provider = AsyncMock()
        provider.dimension = 384
        provider.embed.return_value = [0.1] * 384
        mock.return_value = provider
        yield provider

@pytest.mark.asyncio
async def test_initialize(mock_qdrant, mock_embedding_provider):
    store = MemoryStore()
    await store.initialize()
    
    mock_qdrant.connect.assert_called_once()
    mock_qdrant.create_collection.assert_called_once_with(
        name="agent_memory",
        vector_size=384,
        distance="Cosine"
    )

@pytest.mark.asyncio
async def test_add_memory(mock_qdrant, mock_embedding_provider):
    store = MemoryStore()
    memory = MemoryCreate(
        content="test content",
        role="user",
        agent_id="agent-1",
        user_id="user-1",
        conversation_id="conv-1",
        type="raw"
    )
    
    response = await store.add_memory(memory)
    
    mock_embedding_provider.embed.assert_called_once_with("test content")
    mock_qdrant.upsert.assert_called_once()
    
    # Check payload structure
    args = mock_qdrant.upsert.call_args
    collection_name, points = args[0]
    assert collection_name == "agent_memory"
    assert len(points) == 1
    assert points[0].payload["content"] == "test content"
    assert points[0].payload["conversation_id"] == "conv-1"
    
    assert response.id is not None
    assert response.content == "test content"

@pytest.mark.asyncio
async def test_search_memory(mock_qdrant, mock_embedding_provider):
    store = MemoryStore()
    
    # Mock search return
    mock_point = VectorPoint(
        id="mem-1",
        vector=[0.1]*384,
        payload={
            "content": "found content",
            "role": "user",
            "agent_id": "agent-1",
            "user_id": "user-1",
            "conversation_id": "conv-1",
            "type": "raw",
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        score=0.9
    )
    mock_qdrant.search.return_value = [mock_point]
    
    # Mock embedding return
    mock_embedding_provider.embed.return_value = [0.1] * 384
    
    results = await store.search_memory(
        query="test query",
        filter_params=MemoryFilter(
            agent_id="agent-1",
            user_id="user-1",
            roles=["admin"]
        )
    )
    
    mock_embedding_provider.embed.assert_called_once_with("test query")
    mock_qdrant.search.assert_called_once()
    
    # Check filter logic
    call_kwargs = mock_qdrant.search.call_args[1]
    qdrant_filter = call_kwargs['filter']
    
    # It should be a models.Filter object
    from qdrant_client.http import models
    assert isinstance(qdrant_filter, models.Filter)
    assert len(qdrant_filter.must) == 2 # agent_id + permission_filter
    
    # Check agent_id condition
    agent_cond = qdrant_filter.must[0]
    assert agent_cond.key == "agent_id"
    assert agent_cond.match.value == "agent-1"
    
    # Check permission filter (nested)
    perm_filter = qdrant_filter.must[1]
    assert isinstance(perm_filter, models.Filter)
    assert len(perm_filter.should) == 2
    
    # Check user_id match
    user_cond = perm_filter.should[0]
    assert user_cond.key == "user_id"
    assert user_cond.match.value == "user-1"
    
    # Check access_list match (any of user_id or roles)
    access_cond = perm_filter.should[1]
    assert access_cond.key == "access_list"
    assert set(access_cond.match.any) == {"user-1", "admin"}

    assert len(results) == 1
    assert results[0].content == "found content"

@pytest.mark.asyncio
async def test_delete_memory(mock_qdrant, mock_embedding_provider):
    store = MemoryStore()
    await store.delete_memory("mem-1")
    mock_qdrant.delete.assert_called_once_with("agent_memory", ["mem-1"])
