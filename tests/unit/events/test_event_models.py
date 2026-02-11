"""
Unit tests for Event Bus - Event Models and Schemas.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from orgmind.events import (
    Event,
    EventType,
    ObjectCreatedEvent,
    ObjectUpdatedEvent,
    ObjectDeletedEvent,
    ObjectEventPayload,
    LinkCreatedEvent,
    LinkDeletedEvent,
)


class TestEventModels:
    """Test event model validation and serialization."""
    
    def test_base_event_creation(self):
        """Test creating a base event."""
        tenant_id = uuid4()
        entity_id = uuid4()
        
        event = Event(
            event_type=EventType.OBJECT_CREATED,
            entity_type="object",
            entity_id=entity_id,
            tenant_id=tenant_id,
            payload={"test": "data"},
        )
        
        assert event.event_id is not None
        assert event.event_type == EventType.OBJECT_CREATED
        assert event.entity_id == entity_id
        assert event.tenant_id == tenant_id
        assert isinstance(event.timestamp, datetime)
    
    def test_event_channel_name(self):
        """Test that channel names are correctly formatted."""
        event = Event(
            event_type=EventType.OBJECT_CREATED,
            entity_type="object",
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        
        assert event.channel == "orgmind.object.created"
    
    def test_object_created_event(self):
        """Test ObjectCreatedEvent."""
        object_id = uuid4()
        object_type_id = uuid4()
        tenant_id = uuid4()
        
        event = ObjectCreatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            payload={
                "object_type_id": str(object_type_id),
                "object_id": str(object_id),
                "data": {"name": "Test Object"},
            },
        )
        
        assert event.event_type == EventType.OBJECT_CREATED
        assert event.entity_type == "object"
        assert event.channel == "orgmind.object.created"
    
    def test_object_updated_event_with_changed_fields(self):
        """Test ObjectUpdatedEvent with changed_fields metadata."""
        object_id = uuid4()
        tenant_id = uuid4()
        
        event = ObjectUpdatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            payload={"data": {"name": "Updated Name"}},
            metadata={"changed_fields": ["name", "updated_at"]},
        )
        
        assert event.event_type == EventType.OBJECT_UPDATED
        assert event.changed_fields == ["name", "updated_at"]
    
    def test_object_deleted_event(self):
        """Test ObjectDeletedEvent."""
        object_id = uuid4()
        tenant_id = uuid4()
        
        event = ObjectDeletedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
        )
        
        assert event.event_type == EventType.OBJECT_DELETED
        assert event.entity_type == "object"
    
    def test_link_created_event(self):
        """Test LinkCreatedEvent."""
        link_id = uuid4()
        from_id = uuid4()
        to_id = uuid4()
        tenant_id = uuid4()
        
        event = LinkCreatedEvent(
            entity_id=link_id,
            tenant_id=tenant_id,
            payload={
                "from_object_id": str(from_id),
                "to_object_id": str(to_id),
            },
        )
        
        assert event.event_type == EventType.LINK_CREATED
        assert event.entity_type == "link"
        assert event.channel == "orgmind.link.created"
    
    def test_event_serialization(self):
        """Test that events can be serialized to JSON."""
        object_id = uuid4()
        tenant_id = uuid4()
        
        event = ObjectCreatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            payload={"data": {"name": "Test"}},
        )
        
        # Serialize to JSON
        json_str = event.model_dump_json()
        assert isinstance(json_str, str)
        assert str(object_id) in json_str
        assert "object.created" in json_str
    
    def test_event_deserialization(self):
        """Test that events can be deserialized from JSON."""
        object_id = uuid4()
        tenant_id = uuid4()
        
        event = ObjectCreatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            payload={"data": {"name": "Test"}},
        )
        
        # Serialize then deserialize
        json_str = event.model_dump_json()
        reconstructed = Event.model_validate_json(json_str)
        
        assert reconstructed.event_id == event.event_id
        assert reconstructed.event_type == event.event_type
        assert reconstructed.entity_id == event.entity_id
