import pytest
from unittest.mock import MagicMock, patch
from orgmind.agents.context import ContextBuilder

@pytest.fixture
def mock_neo4j():
    with patch("orgmind.agents.context.Neo4jAdapter") as mock:
        instance = mock.return_value
        instance.execute_read = MagicMock()
        instance.connect = MagicMock()
        yield instance

def test_extract_entities():
    builder = ContextBuilder()
    text = "Tell me about Project Alpha and John Doe."
    entities = builder._extract_entities(text)
    assert "Project Alpha" in entities
    assert "John Doe" in entities
    # 'Tell' is also capitalized at start, so it might be extracted.
    assert len(entities) >= 2

# Removed synchronous test


# Since get_context is async, we need pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

@pytest.mark.asyncio
async def test_get_context_async(mock_neo4j):
    builder = ContextBuilder()
    mock_neo4j.execute_read.return_value = [
        {"source": "A", "relationship": "REL", "target": "B"}
    ]
    context = await builder.get_context("Query about A")
    assert "- A REL B" in context
