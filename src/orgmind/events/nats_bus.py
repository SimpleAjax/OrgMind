"""
NATS JetStream-based Event Bus implementation.

Provides durable, persistent event streaming with consumer groups and replay capabilities.
"""

import asyncio
import json
from typing import Dict

import structlog
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, StreamConfig

from .bus import EventBus, EventHandler
from .event import Event

logger = structlog.get_logger()


class NatsEventBus(EventBus):
    """
    NATS JetStream based event bus implementation.
    
    Provides persistent, durable event streaming with:
    - Message persistence and replay
    - Consumer groups for load balancing
    - At-least-once delivery guarantees
    - Pattern-based subscriptions
    """
    
    STREAM_NAME = "ORGMIND_EVENTS"
    
    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        max_reconnect_attempts: int = 60,
    ):
        """
        Initialize NATS event bus.
        
        Args:
            nats_url: NATS server URL
            max_reconnect_attempts: Maximum reconnection attempts
        """
        self.nats_url = nats_url
        self.max_reconnect_attempts = max_reconnect_attempts
        self.nc: NATS | None = None
        self.js: JetStreamContext | None = None
        self._subscriptions: Dict[str, object] = {}
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection to NATS."""
        if self._connected:
            logger.warning("Already connected to NATS")
            return
        
        try:
            self.nc = NATS()
            await self.nc.connect(
                servers=[self.nats_url],
                max_reconnect_attempts=self.max_reconnect_attempts,
                reconnect_time_wait=2,  # seconds
            )
            
            # Get JetStream context
            self.js = self.nc.jetstream()
            
            # Create or update the events stream
            await self._ensure_stream_exists()
            
            self._connected = True
            logger.info("Connected to NATS JetStream", nats_url=self.nats_url)
        
        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise ConnectionError(f"Could not connect to NATS: {e}")
    
    async def _ensure_stream_exists(self) -> None:
        """Create the ORGMIND_EVENTS stream if it doesn't exist."""
        if not self.js:
            raise RuntimeError("JetStream context not initialized")
        
        try:
            # Try to get existing stream info
            await self.js.stream_info(self.STREAM_NAME)
            logger.debug("Stream already exists", stream=self.STREAM_NAME)
        
        except Exception:
            # Stream doesn't exist, create it
            try:
                stream_config = StreamConfig(
                    name=self.STREAM_NAME,
                    # Capture all orgmind.* subjects
                    subjects=["orgmind.>"],
                    # Retention policy: keep messages for 7 days or 1GB max
                    max_age=7 * 24 * 60 * 60,  # 7 days (library handles nanos)
                    max_bytes=1_000_000_000,  # 1GB
                    # Storage: file-based (persistent)
                    storage="file",
                    # Allow message deduplication by message ID
                    discard="old",
                )
                
                await self.js.add_stream(config=stream_config)
                logger.info("Created JetStream stream", stream=self.STREAM_NAME)
            
            except Exception as e:
                logger.error("Failed to create stream", error=str(e))
                raise
    
    async def disconnect(self) -> None:
        """Close connection to NATS and cleanup subscriptions."""
        if not self._connected:
            return
        
        try:
            # Unsubscribe from all subscriptions
            for sub in self._subscriptions.values():
                try:
                    await sub.unsubscribe()
                except Exception as e:
                    logger.warning("Error unsubscribing", error=str(e))
            
            # Close NATS connection
            if self.nc:
                await self.nc.close()
            
            self._connected = False
            self._subscriptions.clear()
            
            logger.info("Disconnected from NATS JetStream")
        
        except Exception as e:
            logger.error("Error during NATS disconnect", error=str(e))
            raise
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to NATS JetStream.
        
        Args:
            event: Event to publish
        """
        if not self._connected or not self.js:
            raise ConnectionError("Not connected to NATS. Call connect() first.")
        
        try:
            # Serialize event to JSON
            event_json = event.model_dump_json()
            
            # Convert channel to NATS subject (replace dots appropriately)
            # orgmind.object.created -> orgmind.object.created
            subject = event.channel
            
            # Publish to JetStream with message deduplication
            ack = await self.js.publish(
                subject,
                event_json.encode(),
                headers={
                    "Nats-Msg-Id": str(event.event_id),  # Deduplication ID
                    "event-type": event.event_type.value,
                    "entity-type": event.entity_type,
                },
            )
            
            logger.debug(
                "Event published to JetStream",
                event_id=str(event.event_id),
                event_type=event.event_type.value,
                subject=subject,
                stream=ack.stream,
                sequence=ack.seq,
            )
        
        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_id=str(event.event_id),
                error=str(e),
            )
            raise
    
    async def subscribe(
        self,
        channel_pattern: str,
        handler: EventHandler,
        consumer_group: str | None = None,
    ) -> None:
        """
        Subscribe to events matching a channel pattern.
        
        Args:
            channel_pattern: Channel pattern (e.g., "orgmind.object.*")
            handler: Async function to handle received events
            consumer_group: Optional consumer group name for load balancing
        
        Note:
            - Patterns use NATS wildcard syntax: * (single token), > (multiple tokens)
            - Consumer groups enable load balancing across multiple instances
        """
        if not self._connected or not self.js:
            raise ConnectionError("Not connected to NATS. Call connect() first.")
        
        # Convert channel pattern to NATS subject pattern
        # orgmind.object.* -> orgmind.object.*
        # orgmind.> -> matches all orgmind subjects
        subject = channel_pattern
        
        try:
            if consumer_group:
                # Durable consumer with load balancing (queue group)
                consumer_config = ConsumerConfig(
                    durable_name=consumer_group,
                    deliver_policy="all",
                    ack_policy="explicit",
                    max_deliver=3,
                )
                
                subscription = await self.js.subscribe(
                    subject,
                    durable=consumer_group,
                    queue=consumer_group,  # Enable load balancing across instances
                    config=consumer_config,
                    manual_ack=True,  # Changed to True since we manually ack later
                )
            else:
                # Ephemeral consumer (no persistence)
                subscription = await self.js.subscribe(
                    subject,
                    manual_ack=True,  # Consistent behavior
                )
            
            # Store subscription
            self._subscriptions[channel_pattern] = subscription
            
            # Start background task to process messages
            asyncio.create_task(
                self._process_messages(subscription, handler, channel_pattern),
                name=f"nats-sub-{channel_pattern}",
            )
            
            logger.info(
                "Subscribed to event pattern",
                pattern=channel_pattern,
                consumer_group=consumer_group,
                subject=subject,
            )
        
        except Exception as e:
            logger.error(
                "Failed to subscribe to pattern",
                pattern=channel_pattern,
                error=str(e),
            )
            raise
    
    async def _process_messages(
        self,
        subscription: object,
        handler: EventHandler,
        pattern: str,
    ) -> None:
        """
        Background task to process messages from a subscription.
        
        Args:
            subscription: NATS subscription object
            handler: Event handler function
            pattern: Channel pattern being listened to
        """
        logger.info(f"Starting message processor for pattern: {pattern}")
        try:
            async for msg in subscription.messages:
                try:
                    # Parse event from JSON
                    event_data = json.loads(msg.data.decode())
                    event = Event(**event_data)
                    
                    # Call handler
                    await handler(event)
                    
                    # Acknowledge message (for durable consumers)
                    await msg.ack()
                    
                    logger.debug(
                        "Event received and handled",
                        event_id=str(event.event_id),
                        pattern=pattern,
                        subject=msg.subject,
                    )
                
                except Exception as e:
                    logger.error(
                        f"Error handling event: {e}",
                        pattern=pattern,
                        error=str(e),
                        subject=msg.subject,
                        exc_info=True,
                    )
                    # Negative acknowledge to trigger redelivery
                    await msg.nak()
        
        except asyncio.CancelledError:
            logger.info(f"Message processing cancelled for pattern: {pattern}")
            raise
        
        except Exception as e:
            logger.error(
                f"Error in message processor for {pattern}: {e}",
                pattern=pattern,
                error=str(e),
                exc_info=True,
            )
    
    async def unsubscribe(self, channel_pattern: str) -> None:
        """
        Unsubscribe from a channel pattern.
        
        Args:
            channel_pattern: Channel pattern to unsubscribe from
        """
        subscription = self._subscriptions.pop(channel_pattern, None)
        if not subscription:
            return
        
        try:
            await subscription.unsubscribe()
            logger.info("Unsubscribed from pattern", pattern=channel_pattern)
        
        except Exception as e:
            logger.error(
                "Error unsubscribing from pattern",
                pattern=channel_pattern,
                error=str(e),
            )
            raise
    
    async def health_check(self) -> bool:
        """
        Check if NATS is healthy and connected.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self._connected or not self.nc:
            return False
        
        try:
            # Check if connection is still alive
            return self.nc.is_connected
        except Exception:
            return False
