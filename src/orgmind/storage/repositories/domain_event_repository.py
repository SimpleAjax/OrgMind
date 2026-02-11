"""
Event Repository - Repository for domain events persistence and querying.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from orgmind.storage.models import DomainEventModel
from .base import BaseRepository


class DomainEventRepository(BaseRepository[DomainEventModel]):
    """
    Repository for managing domain events in the database.
    
    Provides methods for:
    - Persisting events
    - Querying event history
    - Event replay
    - Audit trail queries
    """
    
    def create(self, session: Session, event: DomainEventModel) -> DomainEventModel:
        """
        Persist a domain event to the database.
        
        Args:
            session: Database session
            event: Event to persist
            
        Returns:
            Persisted event model
        """
        session.add(event)
        session.flush()
        return event
    
    def get_by_id(self, session: Session, event_id: str) -> Optional[DomainEventModel]:
        """Get an event by its ID."""
        return session.get(DomainEventModel, event_id)
    
    def get_events_by_entity(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DomainEventModel]:
        """
        Get all events for a specific entity, ordered by timestamp.
        
        Args:
            session: Database session
            entity_type: Type of entity (e.g., "object", "link")
            entity_id: ID of the entity
            limit: Maximum number of events to return
            offset: Pagination offset
            
        Returns:
            List of events for the entity
        """
        stmt = (
            select(DomainEventModel)
            .where(
                and_(
                    DomainEventModel.entity_type == entity_type,
                    DomainEventModel.entity_id == entity_id,
                )
            )
            .order_by(desc(DomainEventModel.timestamp))
            .limit(limit)
            .offset(offset)
        )
        return list(session.scalars(stmt).all())
    
    def get_events_by_type(
        self,
        session: Session,
        event_type: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DomainEventModel]:
        """
        Get all events of a specific type for a tenant.
        
        Args:
            session: Database session
            event_type: Type of event (e.g., "object.created")
            tenant_id: Tenant ID for multi-tenancy
            limit: Maximum number of events to return
            offset: Pagination offset
            
        Returns:
            List of events of the specified type
        """
        stmt = (
            select(DomainEventModel)
            .where(
                and_(
                    DomainEventModel.event_type == event_type,
                    DomainEventModel.tenant_id == tenant_id,
                )
            )
            .order_by(desc(DomainEventModel.timestamp))
            .limit(limit)
            .offset(offset)
        )
        return list(session.scalars(stmt).all())
    
    def get_events_by_tenant(
        self,
        session: Session,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DomainEventModel]:
        """
        Get all events for a tenant within a time range.
        
        Args:
            session: Database session
            tenant_id: Tenant ID for multi-tenancy
            start_time: Optional start of time range
            end_time: Optional end of time range
            limit: Maximum number of events to return
            offset: Pagination offset
            
        Returns:
            List of events for the tenant
        """
        conditions = [DomainEventModel.tenant_id == tenant_id]
        
        if start_time:
            conditions.append(DomainEventModel.timestamp >= start_time)
        if end_time:
            conditions.append(DomainEventModel.timestamp <= end_time)
        
        stmt = (
            select(DomainEventModel)
            .where(and_(*conditions))
            .order_by(desc(DomainEventModel.timestamp))
            .limit(limit)
            .offset(offset)
        )
        return list(session.scalars(stmt).all())
    
    def get_unpublished_events(
        self,
        session: Session,
        limit: int = 100,
    ) -> List[DomainEventModel]:
        """
        Get events that haven't been successfully published yet.
        
        Useful for retry mechanisms or event replay.
        
        Args:
            session: Database session
            limit: Maximum number of events to return
            
        Returns:
            List of unpublished events
        """
        stmt = (
            select(DomainEventModel)
            .where(DomainEventModel.published == False)
            .order_by(DomainEventModel.timestamp)
            .limit(limit)
        )
        return list(session.scalars(stmt).all())
    
    def mark_as_published(
        self,
        session: Session,
        event_id: str,
        published_at: Optional[datetime] = None,
    ) -> Optional[DomainEventModel]:
        """
        Mark an event as successfully published.
        
        Args:
            session: Database session
            event_id: ID of the event
            published_at: Timestamp when published (defaults to now)
            
        Returns:
            Updated event or None if not found
        """
        event = self.get_by_id(session, event_id)
        if not event:
            return None
        
        event.published = True
        event.published_at = published_at or datetime.utcnow()
        session.flush()
        return event
    
    def count_events(
        self,
        session: Session,
        tenant_id: str,
        event_type: Optional[str] = None,
    ) -> int:
        """
        Count total events for a tenant, optionally filtered by type.
        
        Args:
            session: Database session
            tenant_id: Tenant ID
            event_type: Optional event type filter
            
        Returns:
            Count of events
        """
        conditions = [DomainEventModel.tenant_id == tenant_id]
        if event_type:
            conditions.append(DomainEventModel.event_type == event_type)
        
        stmt = select(DomainEventModel).where(and_(*conditions))
        return session.scalar(select(func.count()).select_from(stmt.subquery()))
    
    # Required abstract method implementations from BaseRepository
    
    def get(self, session: Session, id: str) -> Optional[DomainEventModel]:
        """Get an event by ID (alias for get_by_id)."""
        return self.get_by_id(session, id)
    
    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[DomainEventModel]:
        """Update not supported for events (immutable audit log)."""
        raise NotImplementedError("Events are immutable and cannot be updated")
    
    def delete(self, session: Session, id: str) -> bool:
        """Delete not supported for events (immutable audit log)."""
        raise NotImplementedError("Events are immutable and cannot be deleted")
    
    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[DomainEventModel]:
        """List events ordered by timestamp."""
        stmt = (
            select(DomainEventModel)
            .order_by(desc(DomainEventModel.timestamp))
            .limit(limit)
            .offset(offset)
        )
        return list(session.scalars(stmt).all())
