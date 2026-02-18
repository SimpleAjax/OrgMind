from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, Integer, func

from orgmind.storage.models import Base, JSON_TYPE, TIMESTAMP_TYPE

class RuleModel(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Allows filtering rules by event type efficiently
    event_type_filter: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # JSONLogic condition
    condition: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    
    # Action configuration (e.g. {"type": "slack", "config": {...}})
    action_config: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    
    enabled: Mapped[bool] = mapped_column(Boolean, server_default='true', nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, server_default='1')

class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    rule_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rule_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Status: unread, read, archived
    status: Mapped[str] = mapped_column(String, default="unread", index=True)
    
    # Metadata for routing etc.
    data: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, default={})
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE, nullable=True)
