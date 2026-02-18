from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from orgmind.triggers.models import RuleModel
from orgmind.storage.repositories.base import BaseRepository

class RuleRepository(BaseRepository[RuleModel]):
    
    def create(self, session: Session, entity: RuleModel) -> RuleModel:
        session.add(entity)
        session.flush()
        return entity

    def get(self, session: Session, id: str) -> Optional[RuleModel]:
        return session.get(RuleModel, id)

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[RuleModel]:
        stmt = select(RuleModel).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[RuleModel]:
        rule = self.get(session, id)
        if not rule:
            return None
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        rule.version += 1
        session.flush()
        return rule

    def delete(self, session: Session, id: str) -> bool:
        rule = self.get(session, id)
        if rule:
            session.delete(rule)
            session.flush()
            return True
        return False

    def list_by_event_type(self, session: Session, event_type: str) -> List[RuleModel]:
        """Fetch all enabled rules for a specific event type."""
        stmt = select(RuleModel).where(
            RuleModel.event_type_filter == event_type,
            RuleModel.enabled == True
        )
        return list(session.scalars(stmt).all())
