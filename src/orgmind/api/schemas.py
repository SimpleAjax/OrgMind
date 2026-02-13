from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

# --- Object Types ---

class ObjectTypeBase(BaseModel):
    name: str = Field(..., description="Unique name of the object type")
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(..., description="JSON Schema for properties")
    implements: List[str] = Field(default_factory=list, description="Interfaces implemented")
    sensitive_properties: List[str] = Field(default_factory=list)
    default_permissions: Optional[Dict[str, Any]] = None

class ObjectTypeCreate(ObjectTypeBase):
    pass

class ObjectTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    implements: Optional[List[str]] = None
    sensitive_properties: Optional[List[str]] = None
    default_permissions: Optional[Dict[str, Any]] = None

class ObjectTypeResponse(ObjectTypeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    version: int

    class Config:
        from_attributes = True

# --- Objects ---

class ObjectCreate(BaseModel):
    type_id: UUID
    data: Dict[str, Any]
    created_by: Optional[str] = None

class ObjectUpdate(BaseModel):
    data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

class ObjectResponse(BaseModel):
    id: UUID
    type_id: UUID
    data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    version: int

    class Config:
        from_attributes = True
