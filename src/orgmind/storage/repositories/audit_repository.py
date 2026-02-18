from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from orgmind.storage.repositories.base import BaseRepository
from orgmind.storage.models_audit import AuditLogModel

class AuditRepository(BaseRepository[AuditLogModel]):
    """Repository for Audit Logs."""

    def create(self, session: Session, entity: AuditLogModel) -> AuditLogModel:
        session.add(entity)
        session.flush()
        return entity

    def get(self, session: Session, id: str) -> Optional[AuditLogModel]:
        return session.get(AuditLogModel, id)

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[AuditLogModel]:
        # Audit logs should generally be immutable, but implementing for BaseRepository compliance
        log = self.get(session, id)
        if not log:
            return None
        for key, value in updates.items():
            setattr(log, key, value)
        session.flush()
        return log

    def delete(self, session: Session, id: str) -> bool:
        # Implementing for completeness, though deletion usually restricted
        log = self.get(session, id)
        if not log:
            return False
        session.delete(log)
        session.flush()
        return True

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[AuditLogModel]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    def create_log(
        self, 
        session: Session, 
        user_id: Optional[str], 
        action: str, 
        resource: str, 
        decision: str, 
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLogModel:
        """Helper to create a log entry."""
        log = AuditLogModel(
            user_id=user_id,
            action=action,
            resource=resource,
            decision=decision,
            reason=reason,
            metadata_context=metadata
        )
        return self.create(session, log)
