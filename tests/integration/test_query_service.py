"""
Integration tests for GraphQueryService.
"""

import pytest
import asyncio
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

from orgmind.storage.models import Base, ObjectModel, LinkModel, ObjectTypeModel, LinkTypeModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.graph.neo4j_adapter import Neo4jAdapter
from orgmind.engine.query_service import GraphQueryService


@pytest.fixture
def db_engine():
    """Create a test database engine (SQLite for simplicity)."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def neo4j():
    """Create and connect to Neo4j."""
    adapter = Neo4jAdapter(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="orgmind_dev",
    )
    adapter.connect()
    adapter.clear_database()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def query_service(neo4j, db_engine):
    """Create a GraphQueryService."""
    repo = ObjectRepository()
    return GraphQueryService(neo4j, repo)


@pytest.mark.integration
class TestGraphQueryService:
    """Test suite for GraphQueryService."""

    def test_get_neighbors_with_enrichment(self, query_service, neo4j, db_session):
        """Test finding neighbors and enriching them with Postgres data."""
        
        # 1. Setup Data
        tenant_id = uuid4()
        type_id = str(uuid4())
        
        # Create objects in Postgres
        alice = ObjectModel(
            id=str(uuid4()), 
            type_id=type_id, 
            data={"role": "Engineer", "level": "Senior"}
        )
        bob = ObjectModel(
            id=str(uuid4()), 
            type_id=type_id, 
            data={"role": "Manager", "level": "Lead"}
        )
        
        db_session.add(alice)
        db_session.add(bob)
        db_session.commit()
        
        # Create nodes in Neo4j (simulating sync)
        # Note: We now flatten data properties.
        neo4j.execute_write(
            """
            CREATE (a:Object {id: $id1, type_id: $type_id, name: 'Alice', role: 'Engineer', level: 'Senior'})
            CREATE (b:Object {id: $id2, type_id: $type_id, name: 'Bob', role: 'Manager', level: 'Lead'})
            CREATE (a)-[r:LINK {id: $link_id, type_id: 'knows_type', since: 2023}]->(b)
            """,
            {
                "id1": alice.id,
                "id2": bob.id,
                "type_id": type_id,
                "link_id": str(uuid4()),
            }
        )
        
        # 2. Execute Query
        result = query_service.get_neighbors(
            session=db_session,
            object_id=alice.id,
            depth=1,
            direction="outgoing"
        )
        
        # 3. Verify Graph Structure
        assert len(result.nodes) == 2
        assert len(result.edges) == 1
        
        # Find nodes
        alice_node = next(n for n in result.nodes if n.id == alice.id)
        bob_node = next(n for n in result.nodes if n.id == bob.id)
        
        # Verify Graph Data (from Neo4j)
        assert alice_node.data["name"] == "Alice"
        assert bob_node.data["name"] == "Bob"
        
        # Verify Enriched Data (from Postgres)
        assert alice_node.details is not None
        assert alice_node.details.data["role"] == "Engineer"
        
        assert bob_node.details is not None
        assert bob_node.details.data["role"] == "Manager"

    def test_find_shortest_path(self, query_service, neo4j, db_session):
        """Test finding shortest path between indirect neighbors."""
        
        # A -> B -> C
        id_a = str(uuid4())
        id_b = str(uuid4())
        id_c = str(uuid4())
        type_id = str(uuid4())
        
        # Create minimal Postgres data
        db_session.add(ObjectModel(id=id_a, type_id=type_id, data={"name": "A"}))
        db_session.add(ObjectModel(id=id_c, type_id=type_id, data={"name": "C"}))
        # Skip creating B in Postgres to test partial enrichment
        
        db_session.commit()
        
        # Create Neo4j path with flattened properties
        neo4j.execute_write(
            """
            CREATE (a:Object {id: $id_a, type_id: $tid, label: 'Node A'})
            CREATE (b:Object {id: $id_b, type_id: $tid, label: 'Node B'})
            CREATE (c:Object {id: $id_c, type_id: $tid, label: 'Node C'})
            CREATE (a)-[:LINK {id: 'l1', type_id: 't'}]->(b)
            CREATE (b)-[:LINK {id: 'l2', type_id: 't'}]->(c)
            """,
            {
                "id_a": id_a,
                "id_b": id_b,
                "id_c": id_c,
                "tid": type_id,
            }
        )
        
        # Execute Path Query
        result = query_service.find_shortest_path(
            session=db_session,
            start_id=id_a,
            end_id=id_c,
            max_depth=3
        )
        
        # Verify Path
        assert len(result.nodes) == 3
        assert len(result.edges) == 2
        
        node_a = next(n for n in result.nodes if n.id == id_a)
        node_b = next(n for n in result.nodes if n.id == id_b)
        node_c = next(n for n in result.nodes if n.id == id_c)
        
        # Check Enrichment
        assert node_a.details is not None
        assert node_a.details.data["name"] == "A"
        
        # Node B should NOT have details (not in Postgres)
        assert node_b.details is None
        assert node_b.data["label"] == "Node B"  # But has graph data
        
        assert node_c.details is not None
        assert node_c.details.data["name"] == "C"
