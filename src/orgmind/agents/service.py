import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from orgmind.storage.models import AgentModel, ConversationModel, MessageModel
from orgmind.storage.models_access_control import UserModel
from orgmind.agents.schemas import AgentCreate, AgentUpdate, ConversationCreate, MessageCreate
from orgmind.storage.repositories.agent_repository import AgentRepository, ConversationRepository

class AgentService:
    def __init__(self, session: Session):
        self.session = session
        self.agent_repo = AgentRepository()
        self.conversation_repo = ConversationRepository()

    # --- Agent Management ---

    def create_agent(self, data: AgentCreate, owner_id: str) -> AgentModel:
        agent = AgentModel(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            scope=data.scope,
            llm_config=data.llm_config,
            parent_agent_id=data.parent_agent_id,
            owner_id=owner_id
        )
        result = self.agent_repo.create(self.session, agent)
        self.session.commit()
        return result

    def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        return self.agent_repo.get(self.session, agent_id)

    def list_agents(self, owner_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[AgentModel]:
        if owner_id:
            return self.agent_repo.list_by_owner(self.session, owner_id, limit, offset)
        return self.agent_repo.list(self.session, limit, offset)

    def update_agent(self, agent_id: str, data: AgentUpdate) -> Optional[AgentModel]:
        updates = data.model_dump(exclude_unset=True)
        result = self.agent_repo.update(self.session, agent_id, updates)
        if result:
            self.session.commit()
        return result

    def delete_agent(self, agent_id: str) -> bool:
        result = self.agent_repo.delete(self.session, agent_id)
        if result:
            self.session.commit()
        return result

    # --- Conversation Management ---

    def create_conversation(self, data: ConversationCreate, user_id: str) -> ConversationModel:
        # Verify agent exists
        if not self.get_agent(data.agent_id):
            raise ValueError(f"Agent with ID {data.agent_id} not found")

        conversation = ConversationModel(
            id=str(uuid.uuid4()),
            agent_id=data.agent_id,
            user_id=user_id,
            title=data.title
        )
        result = self.conversation_repo.create(self.session, conversation)
        self.session.commit()
        return result

    def get_conversation(self, conversation_id: str) -> Optional[ConversationModel]:
        return self.conversation_repo.get(self.session, conversation_id)

    def list_conversations(self, agent_id: str, limit: int = 100, offset: int = 0) -> List[ConversationModel]:
        return self.conversation_repo.list_by_agent(self.session, agent_id, limit, offset)

    def add_message(self, conversation_id: str, data: MessageCreate) -> MessageModel:
        # Verify conversation exists
        if not self.get_conversation(conversation_id):
            raise ValueError(f"Conversation with ID {conversation_id} not found")

        message = MessageModel(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=data.role,
            content=data.content,
            tool_calls=data.tool_calls,
            tool_output=data.tool_output
        )
        result = self.conversation_repo.add_message(self.session, message)
        self.session.commit()
        return result

    def get_conversation_history(self, conversation_id: str) -> List[MessageModel]:
        return self.conversation_repo.get_messages(self.session, conversation_id)

    def get_user_roles(self, user_id: str) -> List[str]:
        """Fetch roles for a given user."""
        user = self.session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return []
        return [role.name for role in user.roles]
