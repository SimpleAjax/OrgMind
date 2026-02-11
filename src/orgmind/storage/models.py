from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Integer, Text, JSON, DateTime, ForeignKey, 
    Index, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

class Base(DeclarativeBase):
    pass

# Helper to support both Postgres JSONB and generic JSON (for SQLite tests)
JSON_TYPE = JSON().with_variant(JSONB, 'postgresql')
TIMESTAMP_TYPE = DateTime(timezone=True).with_variant(TIMESTAMP(timezone=True), 'postgresql')

# --- Object Types ---

class ObjectTypeModel(Base):
    __tablename__ = "object_types"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    implements: Mapped[List[str]] = mapped_column(JSON_TYPE, server_default='[]')
    sensitive_properties: Mapped[List[str]] = mapped_column(JSON_TYPE, server_default='[]')
    default_permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, server_default='1')

# --- Objects ---

class ObjectModel(Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type_id: Mapped[str] = mapped_column(ForeignKey("object_types.id"), nullable=False, index=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String, server_default='active', index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, server_default='1')

    # Relationships
    object_type: Mapped["ObjectTypeModel"] = relationship()

# --- Link Types ---

class LinkTypeModel(Base):
    __tablename__ = "link_types"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(ForeignKey("object_types.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(ForeignKey("object_types.id"), nullable=False)
    cardinality: Mapped[str] = mapped_column(String, server_default='many_to_many')
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())

# --- Links ---

class LinkModel(Base):
    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type_id: Mapped[str] = mapped_column(ForeignKey("link_types.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), nullable=False, index=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String)
    
    __table_args__ = (
        UniqueConstraint('type_id', 'source_id', 'target_id', name='uq_link_source_target_type'),
    )

# --- Sources ---

class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    credentials_ref: Mapped[Optional[str]] = mapped_column(String)
    airbyte_connection_id: Mapped[Optional[str]] = mapped_column(String)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String)
    webhook_path: Mapped[Optional[str]] = mapped_column(String)
    sync_mode: Mapped[str] = mapped_column(String, server_default='incremental')
    sync_frequency_minutes: Mapped[int] = mapped_column(Integer, server_default='15')
    type_mappings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE)
    status: Mapped[str] = mapped_column(String, server_default='pending')
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    records_synced: Mapped[int] = mapped_column(Integer, server_default='0')
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())

# --- Events ---

class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_event_type: Mapped[Optional[str]] = mapped_column(String)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    normalized_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE)
    mapped_object_type: Mapped[Optional[str]] = mapped_column(String)
    mapped_object_id: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, server_default='received', index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, server_default='0')
    received_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
