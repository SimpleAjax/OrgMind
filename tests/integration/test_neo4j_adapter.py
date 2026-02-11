"""
Unit tests for Neo4j adapter.
"""

import pytest
from orgmind.graph import Neo4jAdapter


@pytest.mark.integration
class TestNeo4jAdapter:
    """Test Neo4j adapter basic functionality."""
    
    def test_connection(self):
        """Test connecting to Neo4j."""
        adapter = Neo4jAdapter()
        adapter.connect()
        
        assert adapter.health_check() is True
        
        adapter.disconnect()
    
    def test_create_and_query_node(self):
        """Test creating and querying a node."""
        adapter = Neo4jAdapter()
        adapter.connect()
        adapter.clear_database()
        
        # Create a node
        adapter.execute_write(
            "CREATE (n:TestNode {id: $id, name: $name}) RETURN n",
            {"id": "test123", "name": "Test Node"},
        )
        
        # Query the node
        result = adapter.execute_read(
            "MATCH (n:TestNode {id: $id}) RETURN n",
            {"id": "test123"},
        )
        
        assert len(result) == 1
        assert result[0]["n"]["name"] == "Test Node"
        
        # Clean up
        adapter.clear_database()
        adapter.disconnect()
    
    def test_create_relationship(self):
        """Test creating and querying relationships."""
        adapter = Neo4jAdapter()
        adapter.connect()
        adapter.clear_database()
        
        # Create two nodes and a relationship
        adapter.execute_write(
            """
            CREATE (a:Person {id: 'alice', name: 'Alice'})
            CREATE (b:Person {id: 'bob', name: 'Bob'})
            CREATE (a)-[r:KNOWS]->(b)
            RETURN a, r, b
            """
        )
        
        # Query the relationship
        result = adapter.execute_read(
            """
            MATCH (a:Person {id: 'alice'})-[r:KNOWS]->(b:Person {id: 'bob'})
            RETURN a.name AS from, b.name AS to
            """
        )
        
        assert len(result) == 1
        assert result[0]["from"] == "Alice"
        assert result[0]["to"] == "Bob"
        
        # Clean up
        adapter.clear_database()
        adapter.disconnect()
