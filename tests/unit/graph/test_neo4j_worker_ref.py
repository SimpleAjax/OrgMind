
import pytest
from datetime import datetime
from decimal import Decimal
import json

from orgmind.events import NatsEventBus
from orgmind.graph.neo4j_adapter import Neo4jAdapter
from orgmind.graph.neo4j_index_worker import Neo4jIndexWorker

class TestNeo4jDataFlattening:
    """True unit tests for data transformation logic."""

    @pytest.fixture
    def worker(self):
        # We don't need real deps for testing the static method logic
        return Neo4jIndexWorker(None, None)

    def test_flatten_simple_dict(self, worker):
        """Test basic dictionary flattening."""
        data = {"name": "Alice", "age": 30}
        result = worker._flatten_and_sanitize(data)
        assert result == {"name": "Alice", "age": 30}

    def test_flatten_nested_dict(self, worker):
        """Test recursive flattening with separator."""
        data = {
            "user": {
                "name": "Bob",
                "settings": {"theme": "dark"}
            },
            "active": True
        }
        result = worker._flatten_and_sanitize(data)
        
        assert result["user_name"] == "Bob"
        assert result["user_settings_theme"] == "dark"
        assert result["active"] is True
        assert "user" not in result  # Parent keys removed

    def test_sanitize_mixed_list(self, worker):
        """Test handling of heterogeneous lists (which Neo4j rejects)."""
        data = {
            "tags": ["a", 1, True],  # Mixed types
            "valid_tags": ["a", "b"] # Homogeneous
        }
        result = worker._flatten_and_sanitize(data)
        
        # Mixed list should be stringified using str()
        # "a" -> "a", 1 -> "1", True -> "True"
        assert result["tags"] == ["a", "1", "True"]
        # Homogeneous list stays as is
        assert result["valid_tags"] == ["a", "b"]

    def test_sanitize_complex_objects_in_list(self, worker):
        """Test handling objects inside lists."""
        data = {
            "history": [
                {"event": "login", "ts": 123},
                {"event": "logout", "ts": 456}
            ]
        }
        result = worker._flatten_and_sanitize(data)
        
        # Objects should be JSON dumped strings
        assert isinstance(result["history"][0], str)
        assert "login" in result["history"][0]

    def test_sanitize_unsupported_types(self, worker):
        """Test handling of types not supported by Neo4j natively."""
        data = {
            "price": Decimal("10.50"),
            "event_time": datetime(2023, 1, 1)
        }
        result = worker._flatten_and_sanitize(data)
        
        # Converted to string representation
        assert result["price"] == "10.50"
        assert "2023-01-01" in result["event_time"]

    def test_none_handling(self, worker):
        """Test that None values are skipped (Neo4j doesn't store null props)."""
        data = {"a": 1, "b": None}
        result = worker._flatten_and_sanitize(data)
        
        assert result["a"] == 1
        assert "b" not in result
