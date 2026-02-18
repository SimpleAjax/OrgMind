from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class RuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    event_type_filter: str = Field(..., description="The event type this rule applies to e.g. 'object.created.Task'")
    condition: Dict[str, Any] = Field(..., description="JSONLogic condition")
    action_config: Dict[str, Any] = Field(..., description="Action configuration e.g. {'type': 'slack', 'message': '...'}")
    enabled: bool = True

class RuleCreate(RuleBase):
    pass

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    event_type_filter: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None

class RuleResponse(RuleBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    version: int

    model_config = ConfigDict(from_attributes=True)
