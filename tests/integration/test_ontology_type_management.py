"""
Integration tests for Ontology Type Management (Objects and Links).

These tests verify CRUD operations for Object Types and Link Types,
as well as schema validation during object creation/updates.
"""

import asyncio
import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orgmind.storage.models import Base, ObjectModel, LinkModel, ObjectTypeModel, LinkTypeModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.domain_event_repository import DomainEventRepository
from orgmind.events import NatsEventBus, EventPublisher, Event, EventType
from orgmind.engine import OntologyService


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
async def ontology_service(db_session, event_bus):
    """Create an Ontology Service with repositories and event publisher."""
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
    
    return service


@pytest.mark.integration
@pytest.mark.asyncio
class TestOntologyTypeManagement:
    """Integration tests for Type CRUD and Validation."""
    
    async def test_object_type_crud(self, ontology_service, db_session, event_bus):
        """Test full lifestyle of an Object Type."""
        tenant_id = uuid4()
        user_id = uuid4()
        type_id = str(uuid4())
        
        # 1. Create
        schema = ObjectTypeModel(
            id=type_id,
            name="Employee",
            description="An employee record",
            properties={
                "name": {"type": "string"},
                "age": {"type": "number"},
                "active": {"type": "boolean"}
            }
        )
        
        # Listen for events
        all_events = []
        
        async def capture_event(e: Event):
            all_events.append(e)
            
        await event_bus.subscribe("orgmind.object_type.>", capture_event)
        await asyncio.sleep(0.1)
        
        created = await ontology_service.create_object_type(db_session, schema, tenant_id, user_id)
        assert created.id == type_id
        assert created.name == "Employee"
        
        await asyncio.sleep(0.5)
        # Filter events for this specific type ID
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 1
        assert events[0].event_type == EventType.OBJECT_TYPE_CREATED
        
        # 2. Read
        fetched = ontology_service.get_object_type(db_session, type_id)
        assert fetched is not None
        assert fetched.name == "Employee"
        
        # 3. Update
        updated = await ontology_service.update_object_type(
            db_session, 
            type_id, 
            {"name": "Staff Member", "description": "Updated desc"}, 
            tenant_id, 
            user_id
        )
        assert updated.name == "Staff Member"
        assert updated.description == "Updated desc"
        
        await asyncio.sleep(0.5)
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 2
        assert events[1].event_type == EventType.OBJECT_TYPE_UPDATED
        
        # 4. Delete
        deleted = await ontology_service.delete_object_type(db_session, type_id, tenant_id, user_id)
        assert deleted is True
        
        assert ontology_service.get_object_type(db_session, type_id) is None
        
        await asyncio.sleep(0.5)
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 3
        assert events[2].event_type == EventType.OBJECT_TYPE_DELETED


    async def test_link_type_crud(self, ontology_service, db_session, event_bus):
        """Test full lifecycle of a Link Type."""
        # Setup Object Types first
        t1 = ObjectTypeModel(id=str(uuid4()), name="A", properties={})
        t2 = ObjectTypeModel(id=str(uuid4()), name="B", properties={})
        db_session.add_all([t1, t2])
        db_session.commit()
        
        tenant_id = uuid4()
        type_id = str(uuid4())
        
        # 1. Create
        schema = LinkTypeModel(
            id=type_id,
            name="Manages",
            source_type=t1.id,
            target_type=t2.id
        )
        
        all_events = []
        
        async def capture_link_event(e: Event):
            all_events.append(e)
            
        await event_bus.subscribe("orgmind.link_type.>", capture_link_event)
        await asyncio.sleep(0.1)
        
        created = await ontology_service.create_link_type(db_session, schema, tenant_id)
        assert created.name == "Manages"
        
        await asyncio.sleep(0.5)
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 1
        assert events[0].event_type == EventType.LINK_TYPE_CREATED
        
        # 2. Update
        updated = await ontology_service.update_link_type(
            db_session, 
            type_id, 
            {"name": "Supervises"}, 
            tenant_id
        )
        assert updated.name == "Supervises"
        
        await asyncio.sleep(0.5)
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 2
        assert events[1].event_type == EventType.LINK_TYPE_UPDATED
        
        # 3. Delete
        await ontology_service.delete_link_type(db_session, type_id, tenant_id)
        assert ontology_service.get_link_type(db_session, type_id) is None
        
        await asyncio.sleep(0.5)
        events = [e for e in all_events if str(e.entity_id) == type_id]
        
        assert len(events) == 3
        assert events[2].event_type == EventType.LINK_TYPE_DELETED

    async def test_schema_validation(self, ontology_service, db_session):
        """Test that objects are validated against their type schema."""
        tenant_id = uuid4()
        type_id = str(uuid4())
        
        # Define Type
        schema = ObjectTypeModel(
            id=type_id,
            name="ValidatedType",
            properties={
                "str_prop": {"type": "string"},
                "num_prop": {"type": "number"},
                "bool_prop": {"type": "boolean"}
            }
        )
        db_session.add(schema)
        db_session.commit()
        
        # 1. Success case
        valid_obj = ObjectModel(
            id=str(uuid4()),
            type_id=type_id,
            data={
                "str_prop": "hello",
                "num_prop": 42,
                "bool_prop": True
            }
        )
        created = await ontology_service.create_object(db_session, valid_obj, tenant_id)
        assert created is not None
        
        # 2. Failure case - Wrong Type (int for string)
        invalid_obj = ObjectModel(
            id=str(uuid4()),
            type_id=type_id,
            data={
                "str_prop": 123  # Error
            }
        )
        with pytest.raises(ValueError) as exc:
            await ontology_service.create_object(db_session, invalid_obj, tenant_id)
        assert "expected string" in str(exc.value)
        
        # 3. Update Failure
        with pytest.raises(ValueError) as exc:
            await ontology_service.update_object(
                db_session, 
                created.id, 
                {"data": {"num_prop": "not a number"}}, 
                tenant_id
            )
        assert "expected number" in str(exc.value)
