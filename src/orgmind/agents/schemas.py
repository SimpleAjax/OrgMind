from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    scope: Literal["USER", "TEAM", "ORG"] = "USER"
    llm_config: Dict[str, Any] = Field(default_factory=dict, alias="model_config")
    parent_agent_id: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    scope: Optional[Literal["USER", "TEAM", "ORG"]] = None
    llm_config: Optional[Dict[str, Any]] = Field(None, alias="model_config")
    parent_agent_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class AgentResponse(AgentBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class MessageBase(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_output: Optional[str] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationBase(BaseModel):
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    agent_id: str

class ConversationResponse(ConversationBase):
    id: str
    agent_id: str
    user_id: str
    messages: List[MessageResponse] = []
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MemoryBase(BaseModel):
    content: str
    role: Literal["user", "assistant", "system"]
    agent_id: str
    user_id: str
    conversation_id: Optional[str] = None
    type: Literal["raw", "summary"] = "raw"
    created_at: Optional[datetime] = None
    access_list: List[str] = Field(default_factory=list)

class MemoryCreate(MemoryBase):
    pass

class MemoryResponse(MemoryBase):
    id: str
    score: Optional[float] = None

class MemoryFilter(BaseModel):
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    type: Optional[Literal["raw", "summary"]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)

