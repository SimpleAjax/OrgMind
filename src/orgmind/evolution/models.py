from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Float, ForeignKey, func, Integer, Text, Boolean
)
from orgmind.storage.models import Base, JSON_TYPE, TIMESTAMP_TYPE

class ScheduledOutcomeStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class OutcomeDefinitionModel(Base):
    """
    Defines what a "successful outcome" looks like.
    e.g. "Email Reply Received", "Jira Task Completed", "SLA Met"
    """
    __tablename__ = "outcome_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Collector type to use (e.g. "email_reply", "task_status")
    collector_type: Mapped[str] = mapped_column(String, nullable=False)
    
    # Configuration for the collector and scorer
    # e.g. { "wait_time_hours": 24, "target_status": "Done" }
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, server_default='{}')
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())

class ScheduledOutcomeModel(Base):
    """
    Represents a scheduled check for an outcome linked to a specific decision.
    """
    __tablename__ = "scheduled_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    # What are we checking?
    definition_id: Mapped[str] = mapped_column(ForeignKey("outcome_definitions.id"), nullable=False)
    
    # Why are we checking? (The decision/action that triggered this)
    trace_id: Mapped[str] = mapped_column(ForeignKey("decision_traces.id"), nullable=False, index=True)
    
    # When should we check?
    scheduled_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, nullable=False, index=True)
    
    # State management
    status: Mapped[str] = mapped_column(String, nullable=False, default=ScheduledOutcomeStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    definition: Mapped["OutcomeDefinitionModel"] = relationship()
    events: Mapped[List["OutcomeEventModel"]] = relationship(back_populates="scheduled_outcome", cascade="all, delete-orphan")

class OutcomeEventModel(Base):
    """
    Records the actual result of an outcome check.
    """
    __tablename__ = "outcome_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    scheduled_outcome_id: Mapped[str] = mapped_column(ForeignKey("scheduled_outcomes.id"), nullable=False, index=True)
    
    # The raw data collected (e.g. { "reply_received": true, "reply_time": "..." })
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    
    # Computed success score (0.0 to 1.0)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Human readable explanation or finding
    summary: Mapped[Optional[str]] = mapped_column(Text)
    
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    
    # Relationships
    scheduled_outcome: Mapped["ScheduledOutcomeModel"] = relationship(back_populates="events")
