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
