from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Integer, Text, ForeignKey, func, Float
)
from orgmind.storage.models import Base, JSON_TYPE, TIMESTAMP_TYPE

class DecisionTraceModel(Base):
    """
    Captures the execution trace of a decision/action taken by the system.
    """
    __tablename__ = "decision_traces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    # What triggered this?
    rule_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    trigger_event_id: Mapped[Optional[str]] = mapped_column(String, index=True) # ID of the event that triggered the rule
    
    # What was done?
    action_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    input_payload: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    output_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE)
    
    # Performance & Status
    status: Mapped[str] = mapped_column(String, server_default='success', index=True) # success, failure
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    
    # When?
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), index=True)
    
    # Context
    snapshot_id: Mapped[Optional[str]] = mapped_column(ForeignKey("context_snapshots.id"), nullable=True)
    
    # Relationships
    snapshot: Mapped[Optional["ContextSnapshotModel"]] = relationship(back_populates="traces")


class ContextSnapshotModel(Base):
    """
    Captures the state of the world (entities and graph) at the time of a decision.
    """
    __tablename__ = "context_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    # What entities were involved?
    entity_states: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False) # Map of entity_id -> state dict
    
    # Graph context (2-hop neighborhood usually)
    graph_neighborhood: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False) # Node/Edge list or similar structure
    
    # When?
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    
    # Relationships
    traces: Mapped[List["DecisionTraceModel"]] = relationship(back_populates="snapshot")
