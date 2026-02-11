from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from orgmind.storage.models import LinkModel, LinkTypeModel
from .base import BaseRepository

class LinkRepository(BaseRepository[LinkModel]):
    """Repository for managing Links and LinkTypes."""

    # --- Link Types ---
    def create_type(self, session: Session, schema: LinkTypeModel) -> LinkTypeModel:
        session.add(schema)
        session.flush()
        return schema

    def get_type(self, session: Session, id: str) -> Optional[LinkTypeModel]:
        return session.get(LinkTypeModel, id)

    # --- Link Instances ---
    
    def create(self, session: Session, link: LinkModel) -> LinkModel:
        session.add(link)
        session.flush()
        return link

    def get(self, session: Session, id: str) -> Optional[LinkModel]:
        return session.get(LinkModel, id)

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[LinkModel]:
        link = self.get(session, id)
        if not link:
            return None
            
        if 'data' in updates and updates['data']:
            new_data = link.data.copy()
            new_data.update(updates['data'])
            link.data = new_data
            
        return link

    def delete(self, session: Session, id: str) -> bool:
        link = self.get(session, id)
        if link:
            session.delete(link)
            return True
        return False

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[LinkModel]:
        stmt = select(LinkModel).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    def get_related(self, session: Session, source_id: str, link_type_id: Optional[str] = None) -> List[LinkModel]:
        stmt = select(LinkModel).where(LinkModel.source_id == source_id)
        if link_type_id:
            stmt = stmt.where(LinkModel.type_id == link_type_id)
        return list(session.scalars(stmt).all())
