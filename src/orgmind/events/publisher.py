"""
Event Publisher Service - High-level interface for publishing domain events.
"""

from typing import Any, Dict, Optional
from uuid import UUID
import logging

from .bus import EventBus
from .event import (
    Event,
    EventType,
    ObjectCreatedEvent,
    ObjectUpdatedEvent,
    ObjectDeletedEvent,
    LinkCreatedEvent,
    LinkDeletedEvent,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    High-level service for publishing domain events.
    
    This service wraps the EventBus and provides a convenient interface
    for publishing typed events from the Ontology Engine.
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def publish_object_created(
        self,
        object_id: UUID,
        object_type_id: UUID,
        data: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object.created event."""
        event = ObjectCreatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "object_type_id": str(object_type_id),
                "object_id": str(object_id),
                "data": data,
            },
        )
        
        logger.info(
            "Publishing object.created event",
            extra={
                "event_id": str(event.event_id),
                "object_id": str(object_id),
                "object_type_id": str(object_type_id),
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    async def publish_object_updated(
        self,
        object_id: UUID,
        object_type_id: UUID,
        data: Dict[str, Any],
        changed_fields: list[str],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object.updated event."""
        event = ObjectUpdatedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "object_type_id": str(object_type_id),
                "object_id": str(object_id),
                "data": data,
            },
            metadata={
                "changed_fields": changed_fields,
            },
        )
        
        logger.info(
            "Publishing object.updated event",
            extra={
                "event_id": str(event.event_id),
                "object_id": str(object_id),
                "changed_fields": changed_fields,
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    async def publish_object_deleted(
        self,
        object_id: UUID,
        object_type_id: UUID,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object.deleted event."""
        event = ObjectDeletedEvent(
            entity_id=object_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "object_type_id": str(object_type_id),
                "object_id": str(object_id),
            },
        )
        
        logger.info(
            "Publishing object.deleted event",
            extra={
                "event_id": str(event.event_id),
                "object_id": str(object_id),
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    async def publish_link_created(
        self,
        link_id: UUID,
        link_type_id: UUID,
        source_id: UUID,
        target_id: UUID,
        data: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish a link.created event."""
        event = LinkCreatedEvent(
            entity_id=link_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "link_type_id": str(link_type_id),
                "link_id": str(link_id),
                "from_object_id": str(source_id),
                "to_object_id": str(target_id),
                "data": data,
            },
        )
        
        logger.info(
            "Publishing link.created event",
            extra={
                "event_id": str(event.event_id),
                "link_id": str(link_id),
                "source_id": str(source_id),
                "target_id": str(target_id),
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    async def publish_link_deleted(
        self,
        link_id: UUID,
        link_type_id: UUID,
        source_id: UUID,
        target_id: UUID,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish a link.deleted event."""
        event = LinkDeletedEvent(
            entity_id=link_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "link_type_id": str(link_type_id),
                "link_id": str(link_id),
                "from_object_id": str(source_id),
                "to_object_id": str(target_id),
            },
        )
        
        logger.info(
            "Publishing link.deleted event",
            extra={
                "event_id": str(event.event_id),
                "link_id": str(link_id),
            },
        )
        
        await self.event_bus.publish(event)
        return event

    # --- Object Type Events ---

    async def publish_object_type_created(
        self,
        type_id: UUID,
        name: str,
        properties: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object_type.created event."""
        event = Event(
            event_type=EventType.OBJECT_TYPE_CREATED,
            entity_type="object_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "name": name,
                "properties": properties,
            },
        )
        await self.event_bus.publish(event)
        return event

    async def publish_object_type_updated(
        self,
        type_id: UUID,
        updates: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object_type.updated event."""
        event = Event(
            event_type=EventType.OBJECT_TYPE_UPDATED,
            entity_type="object_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={"updates": updates},
        )
        await self.event_bus.publish(event)
        return event

    async def publish_object_type_deleted(
        self,
        type_id: UUID,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish an object_type.deleted event."""
        event = Event(
            event_type=EventType.OBJECT_TYPE_DELETED,
            entity_type="object_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={},
        )
        await self.event_bus.publish(event)
        return event

    # --- Link Type Events ---

    async def publish_link_type_created(
        self,
        type_id: UUID,
        name: str,
        source_type: str,
        target_type: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish a link_type.created event."""
        event = Event(
            event_type=EventType.LINK_TYPE_CREATED,
            entity_type="link_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "name": name,
                "source_type": source_type,
                "target_type": target_type,
            },
        )
        await self.event_bus.publish(event)
        return event

    async def publish_link_type_updated(
        self,
        type_id: UUID,
        updates: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish a link_type.updated event."""
        event = Event(
            event_type=EventType.LINK_TYPE_UPDATED,
            entity_type="link_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={"updates": updates},
        )
        await self.event_bus.publish(event)
        return event

    async def publish_link_type_deleted(
        self,
        type_id: UUID,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Event:
        """Publish a link_type.deleted event."""
        event = Event(
            event_type=EventType.LINK_TYPE_DELETED,
            entity_type="link_type",
            entity_id=type_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={},
        )
        await self.event_bus.publish(event)
        return event
