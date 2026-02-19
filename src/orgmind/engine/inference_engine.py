import logging
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.storage.models_traces import (
    DecisionTraceModel, 
    ContextSnapshotModel, 
    InferenceRuleModel, 
    ContextSuggestionModel
)

logger = logging.getLogger(__name__)

class SignalCheck(ABC):
    """Base class for different types of signal checks."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the signal check type."""
        pass

    @abstractmethod
    def evaluate(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel, config: Dict[str, Any]) -> bool:
        """
        Evaluate if the signal is present.
        
        Args:
            trace: The decision trace being analyzed.
            snapshot: The context snapshot associated with the trace.
            config: Configuration for this specific check (from rule definition).
            
        Returns:
            True if signal is detected, False otherwise.
        """
        pass

class FieldChangeSignal(SignalCheck):
    """Checks if a specific field changed in the input vs previous state (if available) or just based on action input."""
    name = "field_change"

    def evaluate(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel, config: Dict[str, Any]) -> bool:
        field_name = config.get("field")
        target_value = config.get("value")
        
        # Simple check: Does the input payload contain this field with this value?
        # A more complex version would compare with previous state in snapshot.
        if not field_name:
            return False
            
        input_data = trace.input_payload or {}
        
        # Check if field exists in input
        if field_name not in input_data:
            return False
            
        # If value is specified, check against it
        if target_value is not None:
             # Handle simple equality for now
            return input_data[field_name] == target_value
            
        return True # Field is present (changed/set)

class TemporalSignal(SignalCheck):
    """Checks for temporal conditions (e.g. "is Friday", "is end of month")."""
    name = "temporal"
    
    def evaluate(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel, config: Dict[str, Any]) -> bool:
        condition = config.get("condition")
        timestamp = trace.timestamp
        
        if condition == "is_weekend":
            return timestamp.weekday() >= 5
        elif condition == "is_friday":
            return timestamp.weekday() == 4
        elif condition == "is_failed":
             return trace.status == "failure"
             
             
        return False

class GraphSignal(SignalCheck):
    """Checks for patterns in the knowledge graph snapshot (e.g. relation exists)."""
    name = "graph_pattern"
    
    def evaluate(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel, config: Dict[str, Any]) -> bool:
        if not snapshot or not snapshot.graph_neighborhood:
            return False
            
        # config example: { "relationship": "BLOCKS", "direction": "outgoing" }
        target_rel = config.get("relationship")
        
        nodes = snapshot.graph_neighborhood.get("nodes", [])
        rels = snapshot.graph_neighborhood.get("relationships", [])
        
        # Simple check: Does any relationship of this type exist in the captured neighborhood?
        for r in rels:
            if r.get("type") == target_rel:
                return True
                
        return False

class InferenceEngine:
    """
    Analyzes Decision Traces to infer WHY they happened.
    """
    
    def __init__(self, postgres_adapter: PostgresAdapter):
        self.postgres = postgres_adapter
        self.signals: Dict[str, SignalCheck] = {
            s.name: s() for s in [FieldChangeSignal, TemporalSignal, GraphSignal]
        }

    def register_signal(self, signal: SignalCheck):
        self.signals[signal.name] = signal

    def evaluate_trace(self, trace_id: str) -> List[str]:
        """
        Main entry point to run inference on a trace.
        
        Returns:
            List of suggestion IDs created.
        """
        created_suggestion_ids = []
        
        with self.postgres.get_session() as session:
            # 1. Fetch Trace & Snapshot
            trace = session.query(DecisionTraceModel).filter_by(id=trace_id).first()
            if not trace:
                logger.error(f"Trace {trace_id} not found")
                return []
                
            snapshot = None
            if trace.snapshot_id:
                snapshot = session.query(ContextSnapshotModel).filter_by(id=trace.snapshot_id).first()
            
            # 2. Fetch Active Rules
            rules = session.query(InferenceRuleModel).filter_by(is_active=True).order_by(InferenceRuleModel.priority.desc()).all()
            
            # 3. Evaluate Rules
            for rule in rules:
                if self._evaluate_rule(rule, trace, snapshot):
                    suggestion_id = self._create_suggestion(session, trace.id, rule)
                    created_suggestion_ids.append(suggestion_id)
            
            session.commit()
            
        return created_suggestion_ids

    def _evaluate_rule(self, rule: InferenceRuleModel, trace: DecisionTraceModel, snapshot: Optional[ContextSnapshotModel]) -> bool:
        """
        Evaluates a single rule against the trace.
        Rule logic is expected to be a Dict like:
        {
            "type": "field_change",
            "config": { "field": "priority", "value": "high" }
        }
        OR a logical combination (AND/OR) - simplified for now to single signal.
        """
        logic = rule.condition_logic
        signal_type = logic.get("type")
        config = logic.get("config", {})
        
        if signal_type in self.signals:
            return self.signals[signal_type].evaluate(trace, snapshot, config)
            
        return False

    def _create_suggestion(self, session, trace_id: str, rule: InferenceRuleModel) -> str:
        suggestion_id = str(uuid.uuid4())
        suggestion = ContextSuggestionModel(
            id=suggestion_id,
            trace_id=trace_id,
            suggestion_text=rule.description or f"Matches rule {rule.name}",
            source=f"rule:{rule.name}",
            confidence=1.0,
            status="pending"
        )
        session.add(suggestion)
        return suggestion_id
