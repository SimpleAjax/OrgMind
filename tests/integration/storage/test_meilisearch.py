import pytest
import uuid
import asyncio
from orgmind.storage.search.meilisearch import MeiliSearchStore

@pytest.fixture
async def search_store():
    store = MeiliSearchStore()
    await store.connect()
    yield store
    await store.close()

@pytest.mark.asyncio
async def test_meilisearch_health_check(search_store):
    assert await search_store.health_check() is True

@pytest.mark.asyncio
async def test_meilisearch_crud(search_store):
    index_name = f"test_index_{uuid.uuid4().hex}"
    
    # 1. Create Index
    created = await search_store.create_index(index_name)
    assert created is True
    
    # 2. Index Documents
    doc_id = str(uuid.uuid4())
    doc = {"id": doc_id, "title": "Test Document", "content": "This is a test document for Meilisearch."}
    
    indexed = await search_store.index_documents(index_name, [doc])
    assert indexed is True
    
    # Wait for indexing (Meilisearch is async)
    await asyncio.sleep(1) 
    
    # 3. Search
    results = await search_store.search(index_name, "test document")
    assert len(results) > 0
    found = False
    for res in results:
        if res.id == doc_id:
            assert res.doc["title"] == "Test Document"
            found = True
            break
    assert found is True
    
    # 4. Delete
    deleted = await search_store.delete_documents(index_name, [doc_id])
    assert deleted is True

    # Wait for deletion
    await asyncio.sleep(1)
    
    # Verify deletion
    results_after = await search_store.search(index_name, query="test document")
    found_after = any(r.id == doc_id for r in results_after)
    assert found_after is False
