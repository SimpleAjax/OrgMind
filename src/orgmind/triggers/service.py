from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session

from orgmind.triggers.models import RuleModel
from orgmind.triggers.repository import RuleRepository
from orgmind.triggers import schemas

class RuleService:
    def __init__(self, repository: RuleRepository):
        self.repository = repository

    def create_rule(self, session: Session, rule_create: schemas.RuleCreate, created_by: Optional[str] = None) -> RuleModel:
        new_rule = RuleModel(
            id=str(uuid4()),
            name=rule_create.name,
            description=rule_create.description,
            event_type_filter=rule_create.event_type_filter,
            condition=rule_create.condition,
            action_config=rule_create.action_config,
            enabled=rule_create.enabled,
            created_by=created_by
        )
        return self.repository.create(session, new_rule)

    def get_rule(self, session: Session, rule_id: str) -> Optional[RuleModel]:
        return self.repository.get(session, rule_id)

    def list_rules(self, session: Session, limit: int = 100, offset: int = 0) -> List[RuleModel]:
        return self.repository.list(session, limit, offset)

    def list_active_rules_by_event(self, session: Session, event_type: str) -> List[RuleModel]:
        """Get enabled rules that match the event type."""
        return self.repository.list_by_event_type(session, event_type)

    def update_rule(self, session: Session, rule_id: str, rule_update: schemas.RuleUpdate) -> Optional[RuleModel]:
        updates = rule_update.model_dump(exclude_unset=True)
        if not updates:
            return self.repository.get(session, rule_id)
            
        return self.repository.update(session, rule_id, updates)

    def delete_rule(self, session: Session, rule_id: str) -> bool:
        return self.repository.delete(session, rule_id)
