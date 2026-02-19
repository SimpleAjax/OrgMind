from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Float, ForeignKey, func
)
from orgmind.storage.models import Base, JSON_TYPE, TIMESTAMP_TYPE

class ContextSourceType(str, Enum):
    BROWSER = "browser"
    SLACK = "slack"
    IDE = "ide"
    JIRA = "jira"
    CALENDAR = "calendar"
    OTHER = "other"

class ContextEventModel(Base):
    """
    Raw context data captured from external sources (Browser, Slack, etc).
    Used to reconstruct what the user was seeing/doing when a decision was made.
    """
    __tablename__ = "context_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    # Source info
    source: Mapped[str] = mapped_column(String, nullable=False, index=True) # e.g. "browser", "slack"
    source_id: Mapped[str] = mapped_column(String, nullable=False, index=True) # External ID (e.g. slack message_ts)
    
    # User linkage
    user_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, index=True) # Grouping ID (e.g. browser session)
    
    # Content
    content: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False) # The actual context payload
    
    # When?
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())

class ContextLinkModel(Base):
    """
    Links a DecisionTrace to relevant ContextEvents.
    Established by the CorrelationWorker.
    """
    __tablename__ = "context_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    trace_id: Mapped[str] = mapped_column(ForeignKey("decision_traces.id"), nullable=False, index=True)
    context_event_id: Mapped[str] = mapped_column(ForeignKey("context_events.id"), nullable=False, index=True)
    
    # Why was this linked?
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    link_type: Mapped[str] = mapped_column(String, default="temporal") # temporal, semantic, manual
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    
    # Relationships
    context_event: Mapped["ContextEventModel"] = relationship()

class NudgeLogModel(Base):
    """
    Log of nudges sent to users for missing context.
    """
    __tablename__ = "nudge_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trace_id: Mapped[str] = mapped_column(ForeignKey("decision_traces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False) # e.g. "slack:dm", "in-app"
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    status: Mapped[str] = mapped_column(String, default="sent") # sent, responded, ignored
