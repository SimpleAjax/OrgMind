"""
Integration tests for NATS Event Bus.

These tests require a running NATS server with JetStream enabled.
Run `docker compose up -d nats` before running these tests.
"""

import asyncio
import pytest
from uuid import uuid4

from orgmind.events import (
    NatsEventBus,
    Event,
    EventType,
    ObjectCreatedEvent,
)


@pytest.fixture
async def nats_bus():
    """Fixture that provides a connected NATS event bus and purges stream."""
    bus = NatsEventBus(nats_url="nats://localhost:4222")
    await bus.connect()
    
    # Purge stream to ensure clean state for each test
    if bus.js:
        try:
            await bus.js.purge_stream(bus.STREAM_NAME)
        except Exception:
            pass  # Stream might not exist yet
            
    yield bus
    
    # Clean up
    await bus.disconnect()


@pytest.mark.integration
class TestNatsEventBus:
    """Integration tests for NATS Event Bus with JetStream."""
    
    async def test_connect_and_health_check(self, nats_bus):
        """Test connection and health check."""
        assert await nats_bus.health_check()
    
    async def test_publish_event(self, nats_bus):
        """Test publishing an event to JetStream."""
        event = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"data": {"name": "Test Object"}},
        )
        
        # Should not raise
        await nats_bus.publish(event)
    
    async def test_subscribe_and_receive_event(self, nats_bus):
        """Test subscribing to events and receiving them."""
        received_events = []
        
        async def handler(event: Event):
            """Test handler that collects events."""
            received_events.append(event)
        
        # Subscribe to all object events
        # Note: NATS ephemeral consumers might pick up recent messages depending on policy
        # We purged stream in fixture, so should be empty
        await nats_bus.subscribe("orgmind.object.*", handler)
        
        # Give subscription time to settle
        await asyncio.sleep(0.2)
        
        # Publish an event
        test_event = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"data": {"name": "Test Object"}},
        )
        await nats_bus.publish(test_event)
        
        # Wait for event to be received
        await asyncio.sleep(0.5)
        
        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].event_id == test_event.event_id
        assert received_events[0].event_type == EventType.OBJECT_CREATED
    
    async def test_pattern_subscription(self, nats_bus):
        """Test pattern-based subscription filters correctly."""
        object_events = []
        link_events = []
        
        async def object_handler(event: Event):
            object_events.append(event)
        
        async def link_handler(event: Event):
            link_events.append(event)
        
        # Subscribe to different patterns
        await nats_bus.subscribe("orgmind.object.*", object_handler)
        await nats_bus.subscribe("orgmind.link.*", link_handler)
        
        await asyncio.sleep(0.2)
        
        # Publish object event
        object_event = Event(
            event_type=EventType.OBJECT_CREATED,
            entity_type="object",
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await nats_bus.publish(object_event)
        
        # Publish link event
        link_event = Event(
            event_type=EventType.LINK_CREATED,
            entity_type="link",
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await nats_bus.publish(link_event)
        
        await asyncio.sleep(0.5)
        
        # Verify correct routing
        assert len(object_events) == 1
        assert len(link_events) == 1
        assert object_events[0].event_type == EventType.OBJECT_CREATED
        assert link_events[0].event_type == EventType.LINK_CREATED
    
    async def test_unsubscribe(self, nats_bus):
        """Test unsubscribing from events."""
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        pattern = "orgmind.object.*"
        
        # Subscribe
        await nats_bus.subscribe(pattern, handler)
        await asyncio.sleep(0.2)
        
        # Publish event (should be received)
        event1 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await nats_bus.publish(event1)
        await asyncio.sleep(0.3)
        
        # Unsubscribe
        await nats_bus.unsubscribe(pattern)
        await asyncio.sleep(0.2)
        
        # Publish another event (should NOT be received)
        event2 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
        )
        await nats_bus.publish(event2)
        await asyncio.sleep(0.3)
        
        # Should have only received the first event
        assert len(received_events) == 1
        assert received_events[0].event_id == event1.event_id
    
    async def test_consumer_group_load_balancing(self, nats_bus):
        """Test that consumer groups enable load balancing."""
        events_consumer1 = []
        events_consumer2 = []
        
        async def handler1(event: Event):
            events_consumer1.append(event)
        
        async def handler2(event: Event):
            events_consumer2.append(event)
        
        # Use a unique consumer group name for this test run
        consumer_group = f"test-group-{uuid4()}"
        
        await nats_bus.subscribe(
            "orgmind.object.*",
            handler1,
            consumer_group=consumer_group,
        )
        
        # Create second bus for second consumer
        bus2 = NatsEventBus(nats_url="nats://localhost:4222")
        await bus2.connect()
        
        try:
            await bus2.subscribe(
                "orgmind.object.*",
                handler2,
                consumer_group=consumer_group,
            )
            
            await asyncio.sleep(0.2)
            
            # Publish 10 events
            for i in range(10):
                event = ObjectCreatedEvent(
                    entity_id=uuid4(),
                    tenant_id=uuid4(),
                    payload={"index": i},
                )
                await nats_bus.publish(event)
            
            # Wait for all events to be processed
            await asyncio.sleep(1.5)
            
            # Both consumers should have received some events
            # (load balanced, not duplicated)
            total_received = len(events_consumer1) + len(events_consumer2)
            assert len(events_consumer1) > 0
            assert len(events_consumer2) > 0
            assert total_received == 10
            
            print(f"Consumer 1: {len(events_consumer1)}, Consumer 2: {len(events_consumer2)}")
        
        finally:
            await bus2.disconnect()
    
    async def test_message_persistence(self, nats_bus):
        """Test that messages persist and can be replayed."""
        # Publish events before subscribing
        event1 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"name": "First"},
        )
        event2 = ObjectCreatedEvent(
            entity_id=uuid4(),
            tenant_id=uuid4(),
            payload={"name": "Second"},
        )
        
        await nats_bus.publish(event1)
        await nats_bus.publish(event2)
        
        await asyncio.sleep(0.3)
        
        # Now subscribe with a durable consumer
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        # Use unique consumer group to ensure we start fresh
        consumer_group_name = f"replay-test-{uuid4()}"
        
        # Durable consumer should receive all previously published events
        # because we purged stream at start of test
        await nats_bus.subscribe(
            "orgmind.object.*",
            handler,
            consumer_group=consumer_group_name,
        )
        
        # Wait for messages to be delivered
        await asyncio.sleep(1.0)
        
        # Should receive both previously published events
        assert len(received_events) == 2
