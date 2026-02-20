from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Float, ForeignKey, func, Integer, Text, Boolean, UniqueConstraint
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

class EvolutionPolicyModel(Base):
    """
    Represents a learned policy or rule derived from successful outcomes.
    e.g. "If context.day == 'Friday' AND context.user == 'Bob', AVOID 'assign_task'"
    """
    __tablename__ = "evolution_policies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Logic for the policy (JsonLogic or similar)
    condition_logic: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    
    # What action to take? (ALLOW, DENY, WARN, RECOMMEND)
    effect: Mapped[str] = mapped_column(String, nullable=False, default="recommend")
    
    # Recommendation details if effect is RECOMMEND/WARN
    message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Source of this policy (e.g., "pattern_detection", "manual")
    source: Mapped[str] = mapped_column(String, nullable=False)
    pattern_ref: Mapped[Optional[str]] = mapped_column(String) # Reference to the pattern ID if autonomous
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())

class ABExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"

class ABExperimentModel(Base):
    """
    Defines an A/B test for a policy or feature.
    """
    __tablename__ = "ab_experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    status: Mapped[str] = mapped_column(String, nullable=False, default=ABExperimentStatus.DRAFT, index=True)
    
    start_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE)
    end_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP_TYPE)
    
    # e.g., "policy_change", "ui_feature"
    experiment_type: Mapped[str] = mapped_column(String, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    variants: Mapped[List["ABVariantModel"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")

class ABVariantModel(Base):
    """
    A variant within an experiment (e.g., "Control", "Treatment A").
    """
    __tablename__ = "ab_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("ab_experiments.id"), nullable=False, index=True)
    
    name: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Control"
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Configuration specific to this variant
    # e.g. { "policy_id": "123" } or { "button_color": "blue" }
    config: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, server_default='{}')
    
    # Weight for traffic allocation (0-100)
    weight: Mapped[int] = mapped_column(Integer, default=50)
    
    # Relationships
    experiment: Mapped["ABExperimentModel"] = relationship(back_populates="variants")

class ExperimentAssignmentModel(Base):
    """
    Records which entity (user/org) is assigned to which variant.
    Ensures consistent experience.
    """
    __tablename__ = "experiment_assignments"

    # Composite key might be better, but simple ID is easier for ORM
    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    experiment_id: Mapped[str] = mapped_column(ForeignKey("ab_experiments.id"), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("ab_variants.id"), nullable=False, index=True)
    
    # The entity being experimented on (usually user_id or tenant_id)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMP_TYPE, server_default=func.now())
    
    __table_args__ = (
        # Ensure an entity is only assigned to one variant per experiment
        UniqueConstraint('experiment_id', 'entity_id', name='uq_experiment_entity_assignment'),
    )
