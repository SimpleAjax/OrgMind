"""
Event Bus - Abstract interface for pub/sub messaging.
"""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from .event import Event


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(ABC):
    """
    Abstract base class for event bus implementations.
    
    This allows swapping between different message brokers (Redis, RabbitMQ, Kafka, etc.)
    without changing consuming code.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        ...
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the message broker."""
        ...
    
    @abstractmethod
    async def publish(self, event: Event) -> None:
        """
        Publish an event to the event bus.
        
        Args:
            event: Event to publish
        """
        ...
    
    @abstractmethod
    async def subscribe(
        self,
        channel_pattern: str,
        handler: EventHandler,
        consumer_group: str | None = None,
    ) -> None:
        """
        Subscribe to events matching a channel pattern.
        
        Args:
            channel_pattern: Channel pattern to subscribe to (supports wildcards: orgmind.object.*)
            handler: Async function to handle received events
            consumer_group: Optional consumer group for load balancing
        """
        ...
    
    @abstractmethod
    async def unsubscribe(self, channel_pattern: str) -> None:
        """
        Unsubscribe from a channel pattern.
        
        Args:
            channel_pattern: Channel pattern to unsubscribe from
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the event bus is healthy and connected.
        
        Returns:
            True if healthy, False otherwise
        """
        ...
