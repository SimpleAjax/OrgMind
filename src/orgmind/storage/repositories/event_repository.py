from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from orgmind.storage.models import EventModel, SourceModel
from .base import BaseRepository

class EventRepository(BaseRepository[EventModel]):
    """Repository for managing Events and Sources via SQLAlchemy."""

    # --- Sources ---
    def create_source(self, session: Session, source: SourceModel) -> SourceModel:
        session.add(source)
        session.flush()
        return source

    def get_source(self, session: Session, id: str) -> Optional[SourceModel]:
        return session.get(SourceModel, id)

    # --- Events ---
    def create(self, session: Session, event: EventModel) -> EventModel:
        session.add(event)
        session.flush()
        return event

    def get(self, session: Session, id: str) -> Optional[EventModel]:
        return session.get(EventModel, id)

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[EventModel]:
        event = self.get(session, id)
        if not event:
            return None
            
        if 'status' in updates: event.status = updates['status']
        if 'error_message' in updates: event.error_message = updates['error_message']
        if 'retry_count' in updates: event.retry_count = updates['retry_count']
        if 'normalized_payload' in updates: event.normalized_payload = updates['normalized_payload']
        if 'mapped_object_id' in updates: event.mapped_object_id = updates['mapped_object_id']
        
        return event

    def delete(self, session: Session, id: str) -> bool:
        event = self.get(session, id)
        if event:
            session.delete(event)
            return True
        return False

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[EventModel]:
        stmt = select(EventModel).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    def get_pending_events(self, session: Session, limit: int = 100) -> List[EventModel]:
        stmt = select(EventModel).where(EventModel.status == 'received').order_by(EventModel.received_at).limit(limit)
        return list(session.scalars(stmt).all())
