"""
Integration tests for Ontology Service with Event Publishing.

These tests verify that CRUD operations properly publish events to the event bus.
Requires running NATS and PostgreSQL.
"""

import asyncio
import pytest
from uuid import uuid4
from datetime import datetime
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
    
    # Create a test object type
    test_type = ObjectTypeModel(
        id=str(uuid4()),
        name="TestObject",
        description="Test object type",
        properties={
            "name": {"type": "string"},
            "value": {"type": "number"},
        },
    )
    session.add(test_type)
    
    # Create a test link type
    test_link_type = LinkTypeModel(
        id=str(uuid4()),
        name="TestLink",
        description="Test link type",
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
async def ontology_service(db_session, event_bus):
    """Create an Ontology Service with repositories and event publisher."""
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
class TestOntologyServiceEventPublishing:
    """Integration tests for Ontology Service event publishing."""
    
    async def test_create_object_publishes_event(self, ontology_service, event_bus):
        """Test that creating an object publishes object.created event."""
        service, session, test_type, _ = ontology_service
        
        # Set up event listener
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        await event_bus.subscribe("orgmind.object.created", handler)
        await asyncio.sleep(0.2)
        
        # Create an object
        tenant_id = uuid4()
        user_id = uuid4()
        object_id = str(uuid4())
        
        obj = ObjectModel(
            id=object_id,
            type_id=test_type.id,
            data={"name": "Test Object", "value": 42},
            created_by=str(user_id),
        )
        
        created_obj = await service.create_object(
            session=session,
            entity=obj,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        
        # Wait for event to be published and received
        await asyncio.sleep(0.5)
        
        # Verify object was created
        assert created_obj.id == object_id
        assert created_obj.data["name"] == "Test Object"
        
        # Verify event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.OBJECT_CREATED
        assert str(event.entity_id) == object_id
        assert str(event.tenant_id) == str(tenant_id)
        assert str(event.user_id) == str(user_id)
        assert event.payload["data"]["name"] == "Test Object"
    
    async def test_update_object_publishes_event(self, ontology_service, event_bus):
        """Test that updating an object publishes object.updated event with changed fields."""
        service, session, test_type, _ = ontology_service
        
        # Create an object first
        tenant_id = uuid4()
        user_id = uuid4()
        object_id = str(uuid4())
        
        obj = ObjectModel(
            id=object_id,
            type_id=test_type.id,
            data={"name": "Original Name", "value": 42},
        )
        session.add(obj)
        session.commit()
        
        # Set up event listener for updates
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        await event_bus.subscribe("orgmind.object.updated", handler)
        await asyncio.sleep(0.2)
        
        # Update the object
        updates = {
            "data": {"name": "Updated Name", "value": 100},
        }
        
        updated_obj = await service.update_object(
            session=session,
            object_id=object_id,
            updates=updates,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        
        # Wait for event
        await asyncio.sleep(0.5)
        
        # Verify object was updated
        assert updated_obj.data["name"] == "Updated Name"
        assert updated_obj.data["value"] == 100
        
        # Verify event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.OBJECT_UPDATED
        assert str(event.entity_id) == object_id
        
        # Verify changed fields were tracked
        changed_fields = event.metadata.get("changed_fields", [])
        assert "name" in changed_fields
        assert "value" in changed_fields
    
    async def test_delete_object_publishes_event(self, ontology_service, event_bus):
        """Test that deleting an object publishes object.deleted event."""
        service, session, test_type, _ = ontology_service
        
        # Create an object first
        tenant_id = uuid4()
        user_id = uuid4()
        object_id = str(uuid4())
        
        obj = ObjectModel(
            id=object_id,
            type_id=test_type.id,
            data={"name": "To Delete"},
        )
        session.add(obj)
        session.commit()
        
        # Set up event listener
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        await event_bus.subscribe("orgmind.object.deleted", handler)
        await asyncio.sleep(0.2)
        
        # Delete the object
        deleted = await service.delete_object(
            session=session,
            object_id=object_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        
        # Wait for event
        await asyncio.sleep(0.5)
        
        # Verify object was deleted (soft delete)
        assert deleted is True
        obj_from_db = session.get(ObjectModel, object_id)
        assert obj_from_db.status == "deleted"
        
        # Verify event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.OBJECT_DELETED
        assert str(event.entity_id) == object_id
    
    async def test_create_link_publishes_event(self, ontology_service, event_bus):
        """Test that creating a link publishes link.created event."""
        service, session, test_type, test_link_type = ontology_service
        
        # Create two objects to link
        obj1_id = str(uuid4())
        obj2_id = str(uuid4())
        
        obj1 = ObjectModel(id=obj1_id, type_id=test_type.id, data={"name": "Object 1"})
        obj2 = ObjectModel(id=obj2_id, type_id=test_type.id, data={"name": "Object 2"})
        session.add_all([obj1, obj2])
        session.commit()
        
        # Set up event listener
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        await event_bus.subscribe("orgmind.link.created", handler)
        await asyncio.sleep(0.2)
        
        # Create a link
        tenant_id = uuid4()
        user_id = uuid4()
        link_id = str(uuid4())
        
        link = LinkModel(
            id=link_id,
            type_id=test_link_type.id,
            source_id=obj1_id,
            target_id=obj2_id,
            data={"relationship": "related_to"},
        )
        
        created_link = await service.create_link(
            session=session,
            entity=link,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        
        # Wait for event
        await asyncio.sleep(0.5)
        
        # Verify link was created
        assert created_link.id == link_id
        assert created_link.source_id == obj1_id
        assert created_link.target_id == obj2_id
        
        # Verify event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.LINK_CREATED
        assert str(event.entity_id) == link_id
        assert event.payload["from_object_id"] == obj1_id
        assert event.payload["to_object_id"] == obj2_id
    
    async def test_delete_link_publishes_event(self, ontology_service, event_bus):
        """Test that deleting a link publishes link.deleted event."""
        service, session, test_type, test_link_type = ontology_service
        
        # Create two objects to link
        obj1_id = str(uuid4())
        obj2_id = str(uuid4())
        obj1 = ObjectModel(id=obj1_id, type_id=test_type.id, data={"name": "Object 1"})
        obj2 = ObjectModel(id=obj2_id, type_id=test_type.id, data={"name": "Object 2"})
        
        # Create a link
        link_id = str(uuid4())
        link = LinkModel(
            id=link_id,
            type_id=test_link_type.id,
            source_id=obj1_id,
            target_id=obj2_id,
        )
        
        session.add_all([obj1, obj2, link])
        session.commit()
        
        # Set up event listener
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        await event_bus.subscribe("orgmind.link.deleted", handler)
        await asyncio.sleep(0.2)
        
        # Delete the link
        tenant_id = uuid4()
        user_id = uuid4()
        
        deleted = await service.delete_link(
            session=session,
            link_id=link_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        
        # Wait for event
        await asyncio.sleep(0.5)
        
        # Verify link was deleted
        assert deleted is True
        link_from_db = session.get(LinkModel, link_id)
        assert link_from_db is None
        
        # Verify event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.LINK_DELETED
        assert str(event.entity_id) == link_id
    
    async def test_multiple_operations_publish_correct_events(self, ontology_service, event_bus):
        """Test that multiple operations publish the correct sequence of events."""
        service, session, test_type, test_link_type = ontology_service
        
        # Set up event listener for all events
        all_events = []
        
        async def handler(event: Event):
            all_events.append(event)
        
        await event_bus.subscribe("orgmind.>", handler)
        await asyncio.sleep(0.2)
        
        tenant_id = uuid4()
        user_id = uuid4()
        
        # Create object
        obj_id = str(uuid4())
        obj = ObjectModel(id=obj_id, type_id=test_type.id, data={"name": "Test"})
        await service.create_object(session, obj, tenant_id, user_id)
        
        await asyncio.sleep(0.3)
        
        # Update object
        await service.update_object(
            session, obj_id, {"data": {"name": "Updated"}}, tenant_id, user_id
        )
        
        await asyncio.sleep(0.3)
        
        # Delete object
        await service.delete_object(session, obj_id, tenant_id, user_id)
        
        await asyncio.sleep(0.5)
        
        # Verify all events were published in correct order
        assert len(all_events) == 3
        assert all_events[0].event_type == EventType.OBJECT_CREATED
        assert all_events[1].event_type == EventType.OBJECT_UPDATED
        assert all_events[2].event_type == EventType.OBJECT_DELETED
        
        # All events should have the same entity_id
        assert str(all_events[0].entity_id) == obj_id
        assert str(all_events[1].entity_id) == obj_id
        assert str(all_events[2].entity_id) == obj_id
