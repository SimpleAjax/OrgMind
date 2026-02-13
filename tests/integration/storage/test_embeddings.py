import pytest
import os
from orgmind.platform.ai.embeddings import get_embedding_provider, OpenAIEmbeddingProvider, MockEmbeddingProvider

@pytest.mark.asyncio
async def test_embedding_provider_factory(mocker):
    # Case 1: OpenAI Provider requested but No API Key -> Mock
    mocker.patch("orgmind.platform.ai.embeddings.settings.EMBEDDING_PROVIDER", "openai")
    mocker.patch("orgmind.platform.ai.embeddings.settings.OPENAI_API_KEY", "")
    
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)
    
    embedding = await provider.embed("hello world")
    assert len(embedding) == 1536
    assert isinstance(embedding[0], float)

@pytest.mark.asyncio
async def test_mock_embedding_determinism():
    provider = MockEmbeddingProvider()
    e1 = await provider.embed("hello")
    e2 = await provider.embed("hello")
    e3 = await provider.embed("world")
    
    assert e1 == e2
    assert e1 != e3

@pytest.mark.asyncio
async def test_mock_embedding_batch():
    provider = MockEmbeddingProvider()
    texts = ["hello", "world"]
    embeddings = await provider.embed_batch(texts)
    
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536
    assert embeddings[0] == await provider.embed("hello")

@pytest.mark.asyncio
async def test_fastembed_provider(mocker):
    # Mock settings to use local provider
    mocker.patch("orgmind.platform.ai.embeddings.settings.EMBEDDING_PROVIDER", "local")
    mocker.patch("orgmind.platform.ai.embeddings.settings.LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    
    provider = get_embedding_provider()
    
    # Verify type
    # We need to import FastEmbedProvider if not exported in __init__ or available here
    # It is available in orgmind.platform.ai.embeddings
    from orgmind.platform.ai.embeddings import FastEmbedProvider
    assert isinstance(provider, FastEmbedProvider)
    
    # Verify dimension (should be 384 for all-MiniLM-L6-v2)
    assert provider.dimension == 384
    
    # Verify embedding generation
    text = "Hello world"
    embedding = await provider.embed(text)
    assert len(embedding) == 384
    assert isinstance(embedding, list)
    assert all(isinstance(x, float) for x in embedding)
    
    # Verify batch
    texts = ["Hello", "World"]
    embeddings = await provider.embed_batch(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384
