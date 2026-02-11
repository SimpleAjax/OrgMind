"""
Ontology Service - Orchestrates CRUD operations with event publishing.

This service layer sits between the API/Application layer and the Repository layer,
ensuring that all CRUD operations publish appropriate events.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from orgmind.storage.models import ObjectModel, ObjectTypeModel, LinkModel, DomainEventModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.domain_event_repository import DomainEventRepository
from orgmind.events import EventPublisher, Event

logger = logging.getLogger(__name__)


class OntologyService:
    """
    Service layer for Ontology Engine operations with integrated event publishing.
    
    This service ensures that:
    1. All CRUD operations are performed through repositories
    2. Events are published after successful database commits
    3. Proper error handling and logging
    """
    
    def __init__(
        self,
        object_repo: ObjectRepository,
        link_repo: LinkRepository,
        event_repo: DomainEventRepository,
        event_publisher: EventPublisher,
    ):
        self.object_repo = object_repo
        self.link_repo = link_repo
        self.event_repo = event_repo
        self.event_publisher = event_publisher
    
    def _persist_and_publish_event(
        self,
        session: Session,
        event: Event,
    ) -> None:
        """
        Persist an event to database and mark when to publish.
        
        This is a synchronous helper that stores the event in PostgreSQL.
        The actual async publishing happens in the calling method.
        
        Args:
            session: Database session
            event: Event to persist
        """
        domain_event = DomainEventModel(
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            entity_type=event.entity_type,
            entity_id=str(event.entity_id),
            tenant_id=str(event.tenant_id),
            user_id=str(event.user_id) if event.user_id else None,
            payload=event.payload,
            event_metadata=event.metadata,
            timestamp=event.timestamp,
            published=False,  # Will be marked True after successful publish
        )
        
        self.event_repo.create(session, domain_event)
        session.flush()
    
    # --- Object Operations ---
    
    async def create_object(
        self,
        session: Session,
        entity: ObjectModel,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> ObjectModel:
        """
        Create an object and publish object.created event.
        
        Args:
            session: Database session
            entity: Object to create
            tenant_id: Tenant ID for multi-tenancy
            user_id: User performing the action
            
        Returns:
            Created object model
        """
        # Create the object in database
        created_obj = self.object_repo.create(session, entity)
       
        event = None
        # Publish event and get the event object back
        try:
            event = await self.event_publisher.publish_object_created(
                object_id=UUID(created_obj.id),
                object_type_id=UUID(created_obj.type_id),
                data=created_obj.data,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            
            # Persist the event to database BEFORE committing
            self._persist_and_publish_event(session, event)
            
        except Exception as e:
            logger.error(
                f"Failed to publish/persist object.created event for {created_obj.id}",
                exc_info=e,
            )
            # Don't fail the operation if event publishing/persistence fails
            # This is a design decision - events are best-effort
        
        # Commit the transaction (object + event persisted together)
        session.commit()
        
        # Mark event as successfully published
        if event:
            try:
                self.event_repo.mark_as_published(session, str(event.event_id))
                session.commit()
            except Exception as e:
                logger.warning(f"Failed to mark event as published: {e}")
        
        return created_obj
    
    async def update_object(
        self,
        session: Session,
        object_id: str,
        updates: Dict[str, Any],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[ObjectModel]:
        """
        Update an object and publish object.updated event.
        
        Args:
            session: Database session
            object_id: ID of object to update
            updates: Fields to update
            tenant_id: Tenant ID for multi-tenancy
            user_id: User performing the action
            
        Returns:
            Updated object model or None if not found
        """
        # Get original object to determine changed fields
        original = self.object_repo.get(session, object_id)
        if not original:
            return None
        
        original_data = dict(original.data)
        
        # Update the object
        updated_obj = self.object_repo.update(session, object_id, updates)
        if not updated_obj:
            return None
        
        # Commit the transaction
        session.commit()
        
        # Determine changed fields
        changed_fields = []
        if 'data' in updates:
            for key in updates['data'].keys():
                if original_data.get(key) != updates['data'].get(key):
                    changed_fields.append(key)
        
        if 'status' in updates:
            if original.status != updates['status']:
                changed_fields.append('status')
        
        # Publish event after successful commit
        try:
            await self.event_publisher.publish_object_updated(
                object_id=UUID(updated_obj.id),
                object_type_id=UUID(updated_obj.type_id),
                data=updated_obj.data,
                changed_fields=changed_fields,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to publish object.updated event for {updated_obj.id}",
                exc_info=e,
            )
        
        return updated_obj
    
    async def delete_object(
        self,
        session: Session,
        object_id: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Delete (soft delete) an object and publish object.deleted event.
        
        Args:
            session: Database session
            object_id: ID of object to delete
            tenant_id: Tenant ID for multi-tenancy
            user_id: User performing the action
            
        Returns:
            True if deleted, False if not found
        """
        # Get the object before deletion
        obj = self.object_repo.get(session, object_id)
        if not obj:
            return False
        
        object_type_id = obj.type_id
        
        # Delete (soft delete) the object
        deleted = self.object_repo.delete(session, object_id)
        if not deleted:
            return False
        
        # Commit the transaction
        session.commit()
        
        # Publish event after successful commit
        try:
            await self.event_publisher.publish_object_deleted(
                object_id=UUID(object_id),
                object_type_id=UUID(object_type_id),
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to publish object.deleted event for {object_id}",
                exc_info=e,
            )
        
        return True
    
    def get_object(self, session: Session, object_id: str) -> Optional[ObjectModel]:
        """Get an object by ID (no event needed for reads)."""
        return self.object_repo.get(session, object_id)
    
    def list_objects(
        self, session: Session, limit: int = 100, offset: int = 0
    ) -> List[ObjectModel]:
        """List objects (no event needed for reads)."""
        return self.object_repo.list(session, limit, offset)
    
    def list_objects_by_type(
        self, session: Session, type_id: str, limit: int = 100, offset: int = 0
    ) -> List[ObjectModel]:
        """List objects by type (no event needed for reads)."""
        return self.object_repo.list_by_type(session, type_id, limit, offset)
    
    # --- Link Operations ---
    
    async def create_link(
        self,
        session: Session,
        entity: LinkModel,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> LinkModel:
        """
        Create a link and publish link.created event.
        
        Args:
            session: Database session
            entity: Link to create
            tenant_id: Tenant ID for multi-tenancy
            user_id: User performing the action
            
        Returns:
            Created link model
        """
        # Create the link in database
        created_link = self.link_repo.create(session, entity)
        
        # Commit the transaction
        session.commit()
        
        # Publish event after successful commit
        try:
            await self.event_publisher.publish_link_created(
                link_id=UUID(created_link.id),
                link_type_id=UUID(created_link.type_id),
                source_id=UUID(created_link.source_id),
                target_id=UUID(created_link.target_id),
                data=created_link.data,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to publish link.created event for {created_link.id}",
                exc_info=e,
            )
        
        return created_link
    
    async def delete_link(
        self,
        session: Session,
        link_id: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Delete a link and publish link.deleted event.
        
        Args:
            session: Database session
            link_id: ID of link to delete
            tenant_id: Tenant ID for multi-tenancy
            user_id: User performing the action
            
        Returns:
            True if deleted, False if not found
        """
        # Get the link before deletion
        link = self.link_repo.get(session, link_id)
        if not link:
            return False
        
        link_type_id = link.type_id
        source_id = link.source_id
        target_id = link.target_id
        
        # Delete the link
        deleted = self.link_repo.delete(session, link_id)
        if not deleted:
            return False
        
        # Commit the transaction
        session.commit()
        
        # Publish event after successful commit
        try:
            await self.event_publisher.publish_link_deleted(
                link_id=UUID(link_id),
                link_type_id=UUID(link_type_id),
                source_id=UUID(source_id),
                target_id=UUID(target_id),
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to publish link.deleted event for {link_id}",
                exc_info=e,
            )
        
        return True
    
    def get_link(self, session: Session, link_id: str) -> Optional[LinkModel]:
        """Get a link by ID (no event needed for reads)."""
        return self.link_repo.get(session, link_id)
