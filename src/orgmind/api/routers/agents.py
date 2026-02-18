from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from orgmind.api.dependencies import get_db, get_current_user
from orgmind.storage.models_access_control import UserModel
from orgmind.agents.schemas import (
    AgentCreate, AgentUpdate, AgentResponse,
    ConversationCreate, ConversationResponse, MessageCreate, MessageResponse,
    ConversationBase
)
from orgmind.agents.service import AgentService
from orgmind.agents.llm import AgentBrain
from orgmind.agents import basic_tools # Register tools

router = APIRouter(prefix="/agents", tags=["agents"])

# --- Agents ---

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    data: AgentCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # TODO: Enforce permissions/quotas
    return service.create_agent(data, owner_id=current_user.id)

@router.get("", response_model=List[AgentResponse])
def list_agents(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # TODO: Filter by visibility scope
    return service.list_agents(limit=limit, offset=offset)

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # TODO: Verify ownership
    agent = service.update_agent(agent_id, data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # TODO: Verify ownership
    success = service.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return None

# --- Conversations ---

@router.post("/{agent_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def start_conversation(
    agent_id: str,
    data: ConversationBase,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # Manually construct ConversationCreate
    create_data = ConversationCreate(**data.model_dump(), agent_id=agent_id)
    try:
        return service.create_conversation(create_data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{agent_id}/conversations", response_model=List[ConversationResponse])
def list_conversations(
    agent_id: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    return service.list_conversations(agent_id, limit, offset)

@router.get("/{agent_id}/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation_history(
    agent_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Conversation does not belong to this agent")
    
    # Populate messages
    conversation.messages = service.get_conversation_history(conversation_id)
    return conversation

@router.post("/{agent_id}/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    agent_id: str,
    conversation_id: str,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    service = AgentService(db)
    # Verify conversation context
    conversation = service.get_conversation(conversation_id)
    if not conversation:
         raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Conversation does not belong to this agent")
        
    try:
        # Add User Message
        service.add_message(conversation_id, data)
        
        # Trigger Agent
        agent = service.get_agent(agent_id)
        brain = AgentBrain(service)
        response_msg = await brain.process(agent, conversation_id)
        
        return response_msg

    except ValueError as e:
         raise HTTPException(status_code=400, detail=str(e))
