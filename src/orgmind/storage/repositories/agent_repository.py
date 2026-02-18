from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from orgmind.storage.models import AgentModel, ConversationModel, MessageModel
from orgmind.storage.repositories.base import BaseRepository

class AgentRepository(BaseRepository[AgentModel]):
    """Repository for managing Agent entities."""

    def create(self, session: Session, entity: AgentModel) -> AgentModel:
        session.add(entity)
        session.flush()
        session.refresh(entity)
        return entity

    def get(self, session: Session, id: str) -> Optional[AgentModel]:
        return session.execute(select(AgentModel).where(AgentModel.id == id)).scalar_one_or_none()

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[AgentModel]:
        agent = self.get(session, id)
        if not agent:
            return None
        
        for key, value in updates.items():
            setattr(agent, key, value)
        
        session.flush()
        session.refresh(agent)
        return agent

    def delete(self, session: Session, id: str) -> bool:
        agent = self.get(session, id)
        if not agent:
            return False
        session.delete(agent)
        session.flush()
        return True

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[AgentModel]:
        return list(session.execute(select(AgentModel).limit(limit).offset(offset)).scalars().all())

    def list_by_owner(self, session: Session, owner_id: str, limit: int = 100, offset: int = 0) -> List[AgentModel]:
        return list(session.execute(
            select(AgentModel).where(AgentModel.owner_id == owner_id).limit(limit).offset(offset)
        ).scalars().all())

class ConversationRepository(BaseRepository[ConversationModel]):
    """Repository for managing Conversations."""

    def create(self, session: Session, entity: ConversationModel) -> ConversationModel:
        session.add(entity)
        session.flush()
        session.refresh(entity)
        return entity

    def get(self, session: Session, id: str) -> Optional[ConversationModel]:
        return session.execute(select(ConversationModel).where(ConversationModel.id == id)).scalar_one_or_none()

    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[ConversationModel]:
        conv = self.get(session, id)
        if not conv:
            return None
        
        for key, value in updates.items():
            setattr(conv, key, value)
            
        session.flush()
        session.refresh(conv)
        return conv

    def delete(self, session: Session, id: str) -> bool:
        conv = self.get(session, id)
        if not conv:
            return False
        session.delete(conv)
        session.flush()
        return True

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[ConversationModel]:
        return list(session.execute(select(ConversationModel).limit(limit).offset(offset)).scalars().all())

    def list_by_agent(self, session: Session, agent_id: str, limit: int = 100, offset: int = 0) -> List[ConversationModel]:
        return list(session.execute(
            select(ConversationModel)
            .where(ConversationModel.agent_id == agent_id)
            .order_by(desc(ConversationModel.updated_at))
            .limit(limit)
            .offset(offset)
        ).scalars().all())

    def add_message(self, session: Session, message: MessageModel) -> MessageModel:
        session.add(message)
        session.flush()
        session.refresh(message)
        return message
    
    def get_messages(self, session: Session, conversation_id: str, limit: int = 100) -> List[MessageModel]:
         return list(session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
            .limit(limit)
        ).scalars().all())
