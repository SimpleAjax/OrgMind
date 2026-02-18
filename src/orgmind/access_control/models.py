from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

# --- Permissions ---
class PermissionBase(BaseModel):
    name: str = Field(..., description="Unique permission identifier, e.g. 'object.read'")
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class Permission(PermissionBase):
    id: str

    class Config:
        from_attributes = True

# --- Roles ---
class RoleBase(BaseModel):
    name: str = Field(..., description="Unique role name")
    description: Optional[str] = None

class RoleCreate(RoleBase):
    permission_ids: List[str] = []

class Role(RoleBase):
    id: str
    permissions: List[Permission] = []

    class Config:
        from_attributes = True

# --- Users ---
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str # In a real app we'd hash this immediately
    role_ids: List[str] = []

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[str]] = None

class User(UserBase):
    id: str
    roles: List[Role] = []

    class Config:
        from_attributes = True

# --- Policies ---
class PolicyBase(BaseModel):
    name: str
    description: Optional[str] = None
    resource: str
    action: str
    condition: Dict[str, Any]
    effect: str = "allow"
    priority: int = 0

class PolicyCreate(PolicyBase):
    pass

class Policy(PolicyBase):
    id: str

    class Config:
        from_attributes = True
