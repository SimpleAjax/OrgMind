"""
Integration tests for Neo4j graph synchronization.

These tests verify that:
1. Events are correctly translated to Neo4j operations
2. Graph state stays in sync with PostgreSQL
3. Index worker handles all event types
4. Relationship traversal works as expected
"""

import pytest
import asyncio
import json
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orgmind.storage.models import Base, ObjectModel, LinkModel, ObjectTypeModel, LinkTypeModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.domain_event_repository import DomainEventRepository
from orgmind.events import NatsEventBus, EventPublisher
from orgmind.engine import OntologyService
from orgmind.graph import Neo4jAdapter, Neo4jIndexWorker


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
    
    # Create a test object type
    test_type = ObjectTypeModel(
        id=str(uuid4()),
        name="Person",
        description="A person entity",
        properties={
            "name": {"type": "string"},
            "age": {"type": "number"},
        },
    )
    session.add(test_type)
    
    # Create a test link type
    test_link_type = LinkTypeModel(
        id=str(uuid4()),
        name="KNOWS",
        description="Knows relationship",
        source_type=test_type.id,
        target_type=test_type.id,
    )
    session.add(test_link_type)
    session.commit()
    
    yield session, test_type, test_link_type
    
    session.close()


@pytest.fixture
async def event_bus():
    """Create and connect to NATS event bus."""
    bus = NatsEventBus(nats_url="nats://localhost:4222")
    await bus.connect()
    
    # Purge stream for clean state
    if bus.js:
        try:
            await bus.js.purge_stream(bus.STREAM_NAME)
        except Exception:
            pass
    
    yield bus
    
    await bus.disconnect()


@pytest.fixture
async def neo4j():
    """Create and connect to Neo4j."""
    adapter = Neo4jAdapter(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="orgmind_dev",
    )
    adapter.connect()
    
    # Clear database for clean state
    adapter.clear_database()
    
    yield adapter
    
    adapter.disconnect()


@pytest.fixture
async def index_worker(event_bus, neo4j):
    """Create and start the Neo4j Index Worker."""
    worker = Neo4jIndexWorker(event_bus, neo4j)
    await worker.start()
    
    # Give worker time to subscribe and be ready
    await asyncio.sleep(0.8)
    
    yield worker
    
    await worker.stop()


@pytest.fixture
async def ontology_service(db_session, event_bus):
    """Create an Ontology Service."""
    session, test_type, test_link_type = db_session
    
    object_repo = ObjectRepository()
    link_repo = LinkRepository()
    event_repo = DomainEventRepository()
    event_publisher = EventPublisher(event_bus)
    
    service = OntologyService(
        object_repo=object_repo,
        link_repo=link_repo,
        event_repo=event_repo,
        event_publisher=event_publisher,
    )
    
    yield service, session, test_type, test_link_type


@pytest.mark.integration
class TestNeo4jIndexWorker:
    """Test suite for Neo4j Index Worker."""
    
    @pytest.mark.asyncio
    async def test_object_created_syncs_to_graph(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test that creating an object creates a node in Neo4j."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create an object
        obj = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Alice", "age": 30},
        )
        
        created_obj = await service.create_object(
            session=session,
            entity=obj,
            tenant_id=tenant_id,
        )
        
        # Wait for event to be processed by index worker
        await asyncio.sleep(1.5)  # Increased wait time for reliability
        
        # Verify node exists in Neo4j
        result = neo4j.execute_read(
            "MATCH (o:Object {id: $object_id}) RETURN o",
            {"object_id": created_obj.id},
        )
        
        assert len(result) == 1
        node = result[0]["o"]
        assert node["id"] == created_obj.id
        assert node["type_id"] == test_type.id
        assert node["tenant_id"] == str(tenant_id)
        
        assert node["tenant_id"] == str(tenant_id)
        
        # Data is stored as flattened properties
        assert node["name"] == "Alice"
        assert node["age"] == 30
    
    @pytest.mark.asyncio
    async def test_object_updated_syncs_to_graph(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test that updating an object updates the node in Neo4j."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create an object
        obj = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Bob", "age": 25},
        )
        
        created_obj = await service.create_object(
            session=session,
            entity=obj,
            tenant_id=tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        # Update the object
        await service.update_object(
            session=session,
            object_id=created_obj.id,
            updates={"data": {"name": "Bob", "age": 26}},
            tenant_id=tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        # Verify node is updated in Neo4j
        result = neo4j.execute_read(
            "MATCH (o:Object {id: $object_id}) RETURN o",
            {"object_id": created_obj.id},
        )
        
        assert len(result) == 1
        node = result[0]["o"]
        # flattened properties
        assert node["age"] == 26  # Updated value
    
    @pytest.mark.asyncio
    async def test_object_deleted_removes_from_graph(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test that deleting an object removes the node from Neo4j."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create an object
        obj = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Charlie", "age": 35},
        )
        
        created_obj = await service.create_object(
            session=session,
            entity=obj,
            tenant_id=tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        # Verify node exists
        result = neo4j.execute_read(
            "MATCH (o:Object {id: $object_id}) RETURN o",
            {"object_id": created_obj.id},
        )
        assert len(result) == 1
        
        # Delete the object
        await service.delete_object(
            session=session,
            object_id=created_obj.id,
            tenant_id=tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        # Verify node is removed from Neo4j
        result = neo4j.execute_read(
            "MATCH (o:Object {id: $object_id}) RETURN o",
            {"object_id": created_obj.id},
        )
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_link_created_creates_relationship(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test that creating a link creates a relationship in Neo4j."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create two objects
        alice = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Alice"},
        )
        bob = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Bob"},
        )
        
        alice_obj = await service.create_object(session, alice, tenant_id)
        bob_obj = await service.create_object(session, bob, tenant_id)
        
        await asyncio.sleep(0.3)
        
        # Create a link between them
        link = LinkModel(
            id=str(uuid4()),
            type_id=test_link_type.id,
            source_id=alice_obj.id,
            target_id=bob_obj.id,
            data={"since": "2020"},
        )
        
        created_link = await service.create_link(session, link, tenant_id)
        
        await asyncio.sleep(0.5)
        
        # Verify relationship exists in Neo4j
        result = neo4j.execute_read(
            """
            MATCH (from:Object {id: $from_id})-[r:LINK {id: $link_id}]->(to:Object {id: $to_id})
            RETURN r, from, to
            """,
            {
                "from_id": alice_obj.id,
                "link_id": created_link.id,
                "to_id": bob_obj.id,
            },
        )
        
        assert len(result) == 1
        rel = result[0]["r"]
        assert rel["id"] == created_link.id
        assert rel["type_id"] == test_link_type.id
        
        assert rel["id"] == created_link.id
        assert rel["type_id"] == test_link_type.id
        
        # properties are flattened
        assert rel["since"] == "2020"
        
        # Verify we can traverse the relationship
        from_node = result[0]["from"]
        to_node = result[0]["to"]
        
        assert from_node["name"] == "Alice"
        assert to_node["name"] == "Bob"
    
    @pytest.mark.asyncio
    async def test_link_deleted_removes_relationship(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test that deleting a link removes the relationship from Neo4j."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create two objects
        alice = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Alice"},
        )
        bob = ObjectModel(
            id=str(uuid4()),
            type_id=test_type.id,
            data={"name": "Bob"},
        )
        
        alice_obj = await service.create_object(session, alice, tenant_id)
        bob_obj = await service.create_object(session, bob, tenant_id)
        
        await asyncio.sleep(0.3)
        
        # Create a link
        link = LinkModel(
            id=str(uuid4()),
            type_id=test_link_type.id,
            source_id=alice_obj.id,
            target_id=bob_obj.id,
            data={},
        )
        
        created_link = await service.create_link(session, link, tenant_id)
        await asyncio.sleep(0.3)
        
        # Verify relationship exists
        result = neo4j.execute_read(
            "MATCH ()-[r:LINK {id: $link_id}]->() RETURN r",
            {"link_id": created_link.id},
        )
        assert len(result) == 1
        
        # Delete the link
        await service.delete_link(session, created_link.id, tenant_id)
        await asyncio.sleep(0.3)
        
        # Verify relationship is removed
        result = neo4j.execute_read(
            "MATCH ()-[r:LINK {id: $link_id}]->() RETURN r",
            {"link_id": created_link.id},
        )
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_graph_traversal(
        self,
        ontology_service,
        index_worker,
        neo4j,
    ):
        """Test querying relationship paths in the graph."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Create a graph: Alice -> Bob -> Charlie
        alice = await service.create_object(
            session,
            ObjectModel(id=str(uuid4()), type_id=test_type.id, data={"name": "Alice"}),
            tenant_id,
        )
        bob = await service.create_object(
            session,
            ObjectModel(id=str(uuid4()), type_id=test_type.id, data={"name": "Bob"}),
            tenant_id,
        )
        charlie = await service.create_object(
            session,
            ObjectModel(id=str(uuid4()), type_id=test_type.id, data={"name": "Charlie"}),
            tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        # Create links
        await service.create_link(
            session,
            LinkModel(id=str(uuid4()), type_id=test_link_type.id, source_id=alice.id, target_id=bob.id, data={}),
            tenant_id,
        )
        await service.create_link(
            session,
            LinkModel(id=str(uuid4()), type_id=test_link_type.id, source_id=bob.id, target_id=charlie.id, data={}),
            tenant_id,
        )
        
        await asyncio.sleep(0.5)
        
        # Query: Find all people Alice knows (directly or via friends)
        result = neo4j.execute_read(
            """
            MATCH path = (start:Object {id: $alice_id})-[:LINK*1..2]->(friend:Object)
            RETURN properties(friend) AS data, length(path) AS distance
            ORDER BY distance
            """,
            {"alice_id": alice.id},
        )
        
        # Should find Bob (distance 1) and Charlie (distance 2)
        assert len(result) == 2
        
        # data is now a dict because we returned properties(friend)
        bob_data = result[0]["data"]
        charlie_data = result[1]["data"]
        
        assert bob_data["name"] == "Bob"
        assert result[0]["distance"] == 1
        
        assert charlie_data["name"] == "Charlie"
        assert result[1]["distance"] == 2
    
    @pytest.mark.asyncio
    async def test_worker_stats(self, index_worker, neo4j, ontology_service):
        """Test that worker stats are accurate."""
        service, session, test_type, test_link_type = ontology_service
        tenant_id = uuid4()
        
        # Initial stats
        stats = index_worker.get_stats()
        assert stats["nodes"] == 0
        assert stats["relationships"] == 0
        assert stats["healthy"] is True
        
        # Create 2 objects and 1 link
        obj1 = await service.create_object(
            session,
            ObjectModel(id=str(uuid4()), type_id=test_type.id, data={"name": "Node1"}),
            tenant_id,
        )
        obj2 = await service.create_object(
            session,
            ObjectModel(id=str(uuid4()), type_id=test_type.id, data={"name": "Node2"}),
            tenant_id,
        )
        
        await asyncio.sleep(0.3)
        
        await service.create_link(
            session,
            LinkModel(id=str(uuid4()), type_id=test_link_type.id, source_id=obj1.id, target_id=obj2.id, data={}),
            tenant_id,
        )
        
        await asyncio.sleep(0.5)
        
        # Check stats
        stats = index_worker.get_stats()
        assert stats["nodes"] == 2
        assert stats["relationships"] == 1
        assert stats["healthy"] is True
