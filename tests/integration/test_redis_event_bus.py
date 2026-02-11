"""
Integration tests for Redis Event Bus.

These tests require a running Redis instance.
Run `docker compose up -d redis` before running these tests.
"""

import asyncio
import pytest
from uuid import uuid4

from orgmind.events import (
    RedisEventBus,
    Event,
    EventType,
    ObjectCreatedEvent,
)


@pytest.fixture
async def redis_bus():
    """Fixture that provides a connected Redis event bus."""
    bus = RedisEventBus(redis_url="redis://localhost:6379")
    await bus.connect()
    yield bus
    await bus.disconnect()


@pytest.mark.integration
class TestRedisEventBus:
    """Integration tests for Redis Event Bus."""
    
    async def test_connect_and_health_check(self, redis_bus):
        """Test connection and health check."""
        assert await redis_bus.health_check()
    
    async def test_publish_event(self, redis_bus):
        """Test publishing an event."""
        event = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"data": {"name": "Test Object"}},
        )
        
        # Should not raise
        await redis_bus.publish(event)
    
    async def test_subscribe_and_receive_event(self, redis_bus):
        """Test subscribing to events and receiving them."""
        received_events = []
        
        async def handler(event: Event):
            """Test handler that collects events."""
            received_events.append(event)
        
        # Subscribe to all object events
        await redis_bus.subscribe("orgmind.object.*", handler)
        
        # Give subscription time to settle
        await asyncio.sleep(0.1)
        
        # Publish an event
        test_event = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"data": {"name": "Test Object"}},
        )
        await redis_bus.publish(test_event)
        
        # Wait for event to be received
        await asyncio.sleep(0.5)
        
        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].event_id == test_event.event_id
        assert received_events[0].event_type == EventType.OBJECT_CREATED
    
    async def test_pattern_subscription(self, redis_bus):
        """Test pattern-based subscription filters correctly."""
        object_events = []
        link_events = []
        
        async def object_handler(event: Event):
            object_events.append(event)
        
        async def link_handler(event: Event):
            link_events.append(event)
        
        # Subscribe to different patterns
        await redis_bus.subscribe("orgmind.object.*", object_handler)
        await redis_bus.subscribe("orgmind.link.*", link_handler)
        
        await asyncio.sleep(0.1)
        
        # Publish object event
        object_event = Event(
            event_type=EventType.OBJECT_CREATED,
            entity_type="object",
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await redis_bus.publish(object_event)
        
        # Publish link event
        link_event = Event(
            event_type=EventType.LINK_CREATED,
            entity_type="link",
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await redis_bus.publish(link_event)
        
        await asyncio.sleep(0.5)
        
        # Verify correct routing
        assert len(object_events) == 1
        assert len(link_events) == 1
        assert object_events[0].event_type == EventType.OBJECT_CREATED
        assert link_events[0].event_type == EventType.LINK_CREATED
    
    async def test_unsubscribe(self, redis_bus):
        """Test unsubscribing from events."""
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        pattern = "orgmind.object.*"
        
        # Subscribe
        await redis_bus.subscribe(pattern, handler)
        await asyncio.sleep(0.1)
        
        # Publish event (should be received)
        event1 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await redis_bus.publish(event1)
        await asyncio.sleep(0.3)
        
        # Unsubscribe
        await redis_bus.unsubscribe(pattern)
        await asyncio.sleep(0.1)
        
        # Publish another event (should NOT be received)
        event2 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await redis_bus.publish(event2)
        await asyncio.sleep(0.3)
        
        # Should have only received the first event
        assert len(received_events) == 1
        assert received_events[0].event_id == event1.event_id
    
    async def test_multiple_subscribers_receive_same_event(self, redis_bus):
        """Test that pub/sub broadcasts to all subscribers."""
        events_handler1 = []
        events_handler2 = []
        
        async def handler1(event: Event):
            events_handler1.append(event)
        
        async def handler2(event: Event):
            events_handler2.append(event)
        
        # Create two event buses (simulating two different consumers)
        bus2 = RedisEventBus(redis_url="redis://localhost:6379")
        await bus2.connect()
        
        try:
            # Both subscribe to same pattern
            await redis_bus.subscribe("orgmind.object.*", handler1)
            await bus2.subscribe("orgmind.object.*", handler2)
            
            await asyncio.sleep(0.1)
            
            # Publish one event
            event = ObjectCreatedEvent(
                entity_id=uuid4(),
                tenant_id=uuid4(),
            )
            await redis_bus.publish(event)
            
            await asyncio.sleep(0.5)
            
            # Both handlers should receive the event
            assert len(events_handler1) == 1
            assert len(events_handler2) == 1
            assert events_handler1[0].event_id == event.event_id
            assert events_handler2[0].event_id == event.event_id
        
        finally:
            await bus2.disconnect()
