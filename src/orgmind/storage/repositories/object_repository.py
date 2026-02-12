from typing import List, Optional, Dict, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import logging

from orgmind.storage.models import ObjectModel, ObjectTypeModel
from .base import BaseRepository

logger = logging.getLogger(__name__)

class ObjectRepository(BaseRepository[ObjectModel]):
    """Repository for managing Objects and ObjectTypes via SQLAlchemy."""

    # --- Object Types ---
    
    def create_type(self, session: Session, schema: ObjectTypeModel) -> ObjectTypeModel:
        session.add(schema)
        # Flush to check for immediate constraints, caller commits
        session.flush()
        return schema

    def get_type(self, session: Session, type_id: str) -> Optional[ObjectTypeModel]:
        return session.get(ObjectTypeModel, type_id)

    def update_type(self, session: Session, type_id: str, updates: Dict[str, Any]) -> Optional[ObjectTypeModel]:
        obj_type = self.get_type(session, type_id)
        if not obj_type:
            return None
        
        # Update fields if present
        if 'name' in updates:
            obj_type.name = updates['name']
        if 'description' in updates:
            obj_type.description = updates['description']
        if 'properties' in updates:
            obj_type.properties = updates['properties']
        if 'implements' in updates:
            obj_type.implements = updates['implements']
        if 'sensitive_properties' in updates:
            obj_type.sensitive_properties = updates['sensitive_properties']
        if 'default_permissions' in updates:
            obj_type.default_permissions = updates['default_permissions']
            
        obj_type.version += 1
        return obj_type

    def delete_type(self, session: Session, type_id: str) -> bool:
        obj_type = self.get_type(session, type_id)
        if not obj_type:
            return False
        
        session.delete(obj_type)
        return True

    # --- Object Instances ---
    
    def create(self, session: Session, entity: ObjectModel) -> ObjectModel:
        session.add(entity)
        session.flush()
        return entity

    def get(self, session: Session, id: str) -> Optional[ObjectModel]:
        return session.get(ObjectModel, id)

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[ObjectModel]:
        obj = self.get(session, id)
        if not obj:
            return None
            
        # Merge JSON data
        if 'data' in updates and updates['data']:
            # For Postgres JSONB, we might need deep merge or python side merge
            new_data = obj.data.copy()
            new_data.update(updates['data'])
            obj.data = new_data
            
        if 'status' in updates:
            obj.status = updates['status']
            
        obj.version += 1
        return obj

    def delete(self, session: Session, id: str) -> bool:
        obj = self.get(session, id)
        if obj:
            obj.status = 'deleted'
            return True
        return False

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[ObjectModel]:
        stmt = select(ObjectModel).where(ObjectModel.status != 'deleted').limit(limit).offset(offset)
        return list(session.scalars(stmt).all())
        
    def list_by_type(self, session: Session, type_id: str, limit: int = 100, offset: int = 0) -> List[ObjectModel]:
        stmt = select(ObjectModel).where(
            ObjectModel.type_id == type_id, 
            ObjectModel.status != 'deleted'
        ).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    def list_by_ids(self, session: Session, ids: List[str]) -> List[ObjectModel]:
        """Fetch multiple objects by their IDs."""
        if not ids:
            return []
        stmt = select(ObjectModel).where(
            ObjectModel.id.in_(ids),
            ObjectModel.status != 'deleted'
        )
        return list(session.scalars(stmt).all())
