"""
Unit tests for NATS Event Bus reliability (DLQ & Retries).
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from orgmind.events.nats_bus import NatsEventBus
from orgmind.events.event import Event, EventType

# Mock NATS Message
class MockMsg:
    def __init__(self, data, subject="test.subject"):
        self.data = data
        self.subject = subject
        self.ack = AsyncMock()
        self.nak = AsyncMock()
        self.term = AsyncMock()
        
        # Mock metadata structure: metadata.sequence.consumer AND metadata.num_delivered
        self._metadata = MagicMock()
        self._metadata.sequence = MagicMock()
        self._metadata.sequence.consumer = 1 # Default
        self._metadata.num_delivered = 1 # Required by nats_bus.py logic

    @property
    def metadata(self):
        return self._metadata

@pytest.mark.asyncio
async def test_retry_with_backoff():
    """Test that a failed handler triggers NAK with delay."""
    bus = NatsEventBus()
    bus.js = AsyncMock()
    bus._connected = True
    
    # Mock handler that always fails
    async def failing_handler(event):
        raise ValueError("Handler failed")
    
    # Mock subscription
    subscription = MagicMock()
    
    # Create a message
    event = Event(
        event_id="d290f1ee-6c54-4b01-90e6-d701748f0851",
        event_type=EventType.OBJECT_CREATED,
        entity_type="object",
        entity_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        tenant_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        payload={}
    )
    msg = MockMsg(event.model_dump_json().encode())
    # 1st attempt
    msg._metadata.sequence.consumer = 1
    msg._metadata.num_delivered = 1
    
    # We need to simulate the async iterator of subscription.messages
    # This is tricky with simple mocks.
    # Instead, we can verify the _process_messages logic logic by calling the internal logic?
    # Or just mock the iterator.
    
    async def message_iterator():
        yield msg
        
    subscription.messages = message_iterator()
    
    # Run process_messages directly (will exit when iterator is exhausted)
    await bus._process_messages(subscription, failing_handler, "test.*")
    
    # Verify NAK called
    # delay should be 0.5 * 2^(1-1) = 0.5
    print(f"NAK called: {msg.nak.called}")
    print(f"NAK call count: {msg.nak.call_count}")
    if msg.nak.called:
        print(f"NAK call args: {msg.nak.call_args}")

    assert msg.nak.called
    # Check if called with delay (kwargs)
    # The actual call might be nak(delay=0.5) OR sleep + nak() depending on support.
    # Our code tries nak(delay=...) first.
    # mock object supports kwargs capture.
    
    # Note: If `nak` doesn't support delay in mock, it goes into `except TypeError`.
    # But AsyncMock accepts any args.
    call_kwargs = msg.nak.call_args.kwargs
    assert "delay" in call_kwargs
    assert call_kwargs["delay"] == 0.5

@pytest.mark.asyncio
async def test_dlq_after_max_retries():
    """Test that message is moved to DLQ after max retries."""
    bus = NatsEventBus()
    bus.js = AsyncMock()
    bus._connected = True
    
    async def failing_handler(event):
        raise ValueError("Handler failed")
    
    subscription = MagicMock()
    
    event = Event(
        event_id="d290f1ee-6c54-4b01-90e6-d701748f0851",
        event_type=EventType.OBJECT_CREATED,
        entity_type="object",
        entity_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        tenant_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        payload={}
    )
    msg = MockMsg(event.model_dump_json().encode())
    # 6th attempt (max_retries=5)
    msg._metadata.sequence.consumer = 6
    msg._metadata.num_delivered = 6 
    
    async def message_iterator():
        yield msg
        
    subscription.messages = message_iterator()
    
    # Run process_messages directly
    await bus._process_messages(subscription, failing_handler, "test.*")
    
    # Verify published to DLQ
    bus.js.publish.assert_called_once()
    args, kwargs = bus.js.publish.call_args
    assert args[0] == "dlq.test.subject"
    assert "headers" in kwargs
    assert kwargs["headers"]["x-error"] == "Handler failed"
    assert kwargs["headers"]["x-attempts"] == "6"
    
    # Verify original message ACKed
    msg.ack.assert_called_once()
