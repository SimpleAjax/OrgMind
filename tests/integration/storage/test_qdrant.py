import pytest
import uuid
from typing import List, Dict, Any
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.storage.vector.base import VectorPoint

@pytest.fixture
async def vector_store():
    store = QdrantVectorStore()
    await store.connect()
    yield store
    await store.close()

@pytest.mark.asyncio
async def test_qdrant_health_check(vector_store):
    assert await vector_store.health_check() is True

@pytest.mark.asyncio
async def test_qdrant_crud(vector_store):
    collection_name = f"test_collection_{uuid.uuid4().hex}"
    
    # 1. Create Collection
    created = await vector_store.create_collection(collection_name, vector_size=4)
    assert created is True
    
    # 2. Upsert
    point_id = str(uuid.uuid4())
    vector = [0.1, 0.2, 0.3, 0.4]
    payload = {"foo": "bar"}
    
    point = VectorPoint(id=point_id, vector=vector, payload=payload)
    upserted = await vector_store.upsert(collection_name, [point])
    assert upserted is True
    
    # 3. Search
    results = await vector_store.search(collection_name, vector=[0.1, 0.2, 0.3, 0.4], limit=1)
    assert len(results) > 0
    assert results[0].id == point_id
    assert results[0].payload["foo"] == "bar"
    
    # 4. Delete
    deleted = await vector_store.delete(collection_name, [point_id])
    assert deleted is True
    
    # Verify deletion
    results_after = await vector_store.search(collection_name, vector=[0.1, 0.2, 0.3, 0.4], limit=1)
    # Note: Qdrant might have eventual consistency, but usually fast enough for tests
    # We filter specifically for this ID if needed, but here we expect empty or different result
    found_ids = [r.id for r in results_after]
    assert point_id not in found_ids
