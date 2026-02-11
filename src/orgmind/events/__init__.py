"""OrgMind Event Bus - NATS JetStream for event-driven architecture."""

from .bus import EventBus, EventHandler
from .event import (
    Event,
    EventType,
    LinkCreatedEvent,
    LinkDeletedEvent,
    LinkEventPayload,
    ObjectCreatedEvent,
    ObjectDeletedEvent,
    ObjectEventPayload,
    ObjectUpdatedEvent,
)
from .nats_bus import NatsEventBus
from .publisher import EventPublisher
from .redis_bus import RedisEventBus

__all__ = [
    # Core interfaces
    "EventBus",
    "EventHandler",
    "EventPublisher",
    # Event models
    "Event",
    "EventType",
    # Object events
    "ObjectCreatedEvent",
    "ObjectUpdatedEvent",
    "ObjectDeletedEvent",
    "ObjectEventPayload",
    # Link events
    "LinkCreatedEvent",
    "LinkDeletedEvent",
    "LinkEventPayload",
    # Implementations
    "NatsEventBus",  # Primary implementation (recommended)
    "RedisEventBus",  # Legacy/alternative implementation
]

