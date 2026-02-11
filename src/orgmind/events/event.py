"""
Event models and schemas for OrgMind event-driven architecture.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Standard event types."""
    
    # Object events
    OBJECT_CREATED = "object.created"
    OBJECT_UPDATED = "object.updated"
    OBJECT_DELETED = "object.deleted"
    
    # Link events
    LINK_CREATED = "link.created"
    LINK_DELETED = "link.deleted"
    
    # Object Type events
    OBJECT_TYPE_CREATED = "object_type.created"
    OBJECT_TYPE_UPDATED = "object_type.updated"
    OBJECT_TYPE_DELETED = "object_type.deleted"
    
    # Link Type events
    LINK_TYPE_CREATED = "link_type.created"
    LINK_TYPE_UPDATED = "link_type.updated"
    LINK_TYPE_DELETED = "link_type.deleted"
    
    # Ingestion events
    EVENT_INGESTED = "event.ingested"
    
    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


class Event(BaseModel):
    """
    Base event model for all events in OrgMind.
    
    All events published to the event bus must conform to this schema.
    """
    
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    entity_type: str  # e.g., "object", "link", "object_type"
    entity_id: UUID
    tenant_id: UUID
    user_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def channel(self) -> str:
        """Redis channel name for this event."""
        return f"orgmind.{self.event_type.value}"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class ObjectEventPayload(BaseModel):
    """Payload for object-related events."""
    
    object_type_id: UUID
    object_id: UUID
    data: Dict[str, Any]
    tenant_id: UUID
    user_id: Optional[UUID] = None


class ObjectCreatedEvent(Event):
    """Event published when an object is created."""
    
    event_type: Literal[EventType.OBJECT_CREATED] = EventType.OBJECT_CREATED
    entity_type: Literal["object"] = "object"


class ObjectUpdatedEvent(Event):
    """Event published when an object is updated."""
    
    event_type: Literal[EventType.OBJECT_UPDATED] = EventType.OBJECT_UPDATED
    entity_type: Literal["object"] = "object"
    
    @property
    def changed_fields(self) -> list[str]:
        """List of fields that were changed."""
        return self.metadata.get("changed_fields", [])


class ObjectDeletedEvent(Event):
    """Event published when an object is deleted."""
    
    event_type: Literal[EventType.OBJECT_DELETED] = EventType.OBJECT_DELETED
    entity_type: Literal["object"] = "object"


class LinkEventPayload(BaseModel):
    """Payload for link-related events."""
    
    link_type_id: UUID
    link_id: UUID
    from_object_id: UUID
    to_object_id: UUID
    data: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: UUID
    user_id: Optional[UUID] = None


class LinkCreatedEvent(Event):
    """Event published when a link is created."""
    
    event_type: Literal[EventType.LINK_CREATED] = EventType.LINK_CREATED
    entity_type: Literal["link"] = "link"


class LinkDeletedEvent(Event):
    """Event published when a link is deleted."""
    
    event_type: Literal[EventType.LINK_DELETED] = EventType.LINK_DELETED
    entity_type: Literal["link"] = "link"

