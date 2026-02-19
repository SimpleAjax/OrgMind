import uuid
from datetime import datetime
from typing import Any, Dict

from orgmind.events.event import Event, EventType

class EventNormalizer:
    """
    Normalizes external events into internal StandardEvents.
    """
    
    def normalize(self, source: str, event_type: str, payload: Dict[str, Any]) -> Event:
        """
        Normalize a raw event payload into a standard Event.
        """
        # In a real system, we'd have source-specific logic here (e.g. Stripe, Slack, GitHub)
        # For now, we wrap it in a generic event.
        
        return Event(
            event_type=EventType.EVENT_INGESTED,
            entity_type="external_source",
            entity_id=uuid.uuid4(), # Generate a unique ID for this ingestion event
            tenant_id=uuid.uuid4(), # TODO: Extract from auth or payload
            timestamp=datetime.utcnow(),
            payload={
                "source": source,
                "original_type": event_type,
                "data": payload
            },
            metadata={
                "source": source,
                "normalized_at": datetime.utcnow().isoformat()
            }
        )
