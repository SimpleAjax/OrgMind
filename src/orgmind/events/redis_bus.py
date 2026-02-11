"""
Redis-based Event Bus implementation using pub/sub.
"""

import asyncio
import json
from typing import Dict

import redis.asyncio as redis
import structlog

from .bus import EventBus, EventHandler
from .event import Event

logger = structlog.get_logger()


class RedisEventBus(EventBus):
    """
    Redis pub/sub based event bus implementation.
    
    Uses Redis channels for event distribution. Supports pattern-based subscriptions
    using glob-style wildcards (e.g., "orgmind.object.*").
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_connections: int = 10,
    ):
        """
        Initialize Redis event bus.
        
        Args:
            redis_url: Redis connection URL
            max_connections: Maximum number of connections in the pool
        """
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.redis_client: redis.Redis | None = None
        self.pubsub: redis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None
        self._handlers: Dict[str, EventHandler] = {}
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._connected:
            logger.warning("Already connected to Redis")
            return
        
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=self.max_connections,
            )
            
            # Test connection
            await self.redis_client.ping()
            self._connected = True
            
            logger.info("Connected to Redis event bus", redis_url=self.redis_url)
        
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise ConnectionError(f"Could not connect to Redis: {e}")
    
    async def disconnect(self) -> None:
        """Close connection to Redis and cleanup subscriptions."""
        if not self._connected:
            return
        
        try:
            # Cancel listener task
            if self._listener_task:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
            
            # Close pubsub if exists
            if self.pubsub:
                await self.pubsub.close()
            
            # Close Redis client
            if self.redis_client:
                await self.redis_client.close()
            
            self._connected = False
            self._listener_task = None
            self._handlers.clear()
            
            logger.info("Disconnected from Redis event bus")
        
        except Exception as e:
            logger.error("Error during Redis disconnect", error=str(e))
            raise
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to Redis.
        
        Args:
            event: Event to publish
        """
        if not self._connected or not self.redis_client:
            raise ConnectionError("Not connected to Redis. Call connect() first.")
        
        try:
            # Serialize event to JSON
            event_json = event.model_dump_json()
            
            # Publish to the event's channel
            channel = event.channel
            await self.redis_client.publish(channel, event_json)
            
            logger.debug(
                "Event published",
                event_id=str(event.event_id),
                event_type=event.event_type.value,
                channel=channel,
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
            consumer_group: Not used for Redis pub/sub (use Redis Streams for consumer groups)
        
        Note:
            For load balancing across multiple consumers, consider using Redis Streams
            instead of pub/sub. This implementation uses pub/sub which broadcasts to all.
        """
        if not self._connected or not self.redis_client:
            raise ConnectionError("Not connected to Redis. Call connect() first.")
        
        # Create pubsub instance if not exists
        if not self.pubsub:
            self.pubsub = self.redis_client.pubsub()
        
        try:
            # Store handler
            self._handlers[channel_pattern] = handler
            
            # Subscribe to pattern
            await self.pubsub.psubscribe(channel_pattern)
            
            # Start listener task if not already running
            if not self._listener_task or self._listener_task.done():
                self._listener_task = asyncio.create_task(
                    self._listen_to_messages(),
                    name="redis-event-listener",
                )
            
            logger.info(
                "Subscribed to event pattern",
                pattern=channel_pattern,
                consumer_group=consumer_group,
            )
        
        except Exception as e:
            logger.error(
                "Failed to subscribe to pattern",
                pattern=channel_pattern,
                error=str(e),
            )
            raise
    
    async def _listen_to_messages(self) -> None:
        """
        Background task to listen for all messages and route to appropriate handlers.
        
        This is a single listener that handles all subscribed patterns.
        """
        if not self.pubsub:
            return
        
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        # Parse event from JSON
                        event_data = json.loads(message["data"])
                        event = Event(**event_data)
                        
                        # Get the pattern that matched this message
                        matched_pattern = message["pattern"]
                        
                        # Call the handler for this pattern
                        handler = self._handlers.get(matched_pattern)
                        if handler:
                            await handler(event)
                        
                        logger.debug(
                            "Event received and handled",
                            event_id=str(event.event_id),
                            pattern=matched_pattern,
                            channel=message["channel"],
                        )
                    
                    except Exception as e:
                        logger.error(
                            "Error handling event",
                            error=str(e),
                            message=message,
                        )
        
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
            raise
        
        except Exception as e:
            logger.error(
                "Error in event listener",
                error=str(e),
            )
    
    async def unsubscribe(self, channel_pattern: str) -> None:
        """
        Unsubscribe from a channel pattern.
        
        Args:
            channel_pattern: Channel pattern to unsubscribe from
        """
        if not self.pubsub:
            return
        
        try:
            # Unsubscribe from pattern
            await self.pubsub.punsubscribe(channel_pattern)
            
            # Remove handler
            self._handlers.pop(channel_pattern, None)
            
            # If no more handlers, cancel listener task
            if not self._handlers and self._listener_task:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
                self._listener_task = None
            
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
        Check if Redis is healthy and connected.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self._connected or not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False
