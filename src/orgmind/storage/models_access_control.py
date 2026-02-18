from typing import List, Optional, Dict, Any
from sqlalchemy import String, ForeignKey, Table, Column, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from orgmind.storage.models import Base, JSON_TYPE, TIMESTAMP_TYPE

# Associate tables for Many-to-Many relationships
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(String, server_default='true') # SQLite bool compat
    hashed_password: Mapped[Optional[str]] = mapped_column(String) # For local auth if needed
    
    # Relationships
    roles: Mapped[List["RoleModel"]] = relationship(
        secondary=user_roles, 
        back_populates="users",
        lazy="selectin"
    )

class RoleModel(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    users: Mapped[List["UserModel"]] = relationship(
        secondary=user_roles, 
        back_populates="roles",
        lazy="selectin"
    )
    permissions: Mapped[List["PermissionModel"]] = relationship(
        secondary=role_permissions, 
        back_populates="roles",
        lazy="selectin"
    )

class PermissionModel(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False) # e.g. "object.read"
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    roles: Mapped[List["RoleModel"]] = relationship(
        secondary=role_permissions, 
        back_populates="permissions",
        lazy="selectin"
    )

class PolicyModel(Base):
    """
    ABAC Policy definition.
    Allows fine-grained access control based on attributes.
    """
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Scope
    resource: Mapped[str] = mapped_column(String, nullable=False) # e.g. "object_type:task"
    action: Mapped[str] = mapped_column(String, nullable=False) # e.g. "read" or "*"
    
    # Logic
    condition: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False) # JSONLogic
    effect: Mapped[str] = mapped_column(String, server_default='allow') # allow/deny
    
    priority: Mapped[int] = mapped_column(String, server_default='0') # Higher runs first
