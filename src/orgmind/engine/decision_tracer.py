import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.storage.models_traces import DecisionTraceModel
from orgmind.engine.context_capture import ContextSnapshotService

logger = logging.getLogger(__name__)

class DecisionTraceService:
    """
    Service to log execution traces of decisions and actions.
    """
    
    def __init__(self, postgres_adapter: PostgresAdapter, snapshot_service: ContextSnapshotService):
        self.postgres = postgres_adapter
        self.snapshot_service = snapshot_service
        
    def log_decision(
        self, 
        action_type: str,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]] = None,
        rule_id: Optional[str] = None,
        trigger_event_id: Optional[str] = None,
        involved_entity_ids: Optional[List[str]] = None,
        latency_ms: Optional[float] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> str:
        """
        Logs a decision trace, optionally capturing a context snapshot.
        
        Args:
            action_type: name of the action taken (e.g. 'send_slack').
            input_payload: arguments passed to the action.
            output_payload: result from the action.
            rule_id: ID of the rule that triggered this (optional).
            involved_entity_ids: IDs of entities relevant to this decision (for snapshot).
            latency_ms: execution time in ms.
            status: 'success' or 'failure'.
            error_message: error details if failed.
            
        Returns:
            The ID of the created trace.
        """
        trace_id = str(uuid.uuid4())
        
        snapshot_id = None
        if involved_entity_ids:
            try:
                snapshot_id = self.snapshot_service.capture_snapshot(involved_entity_ids)
            except Exception as e:
                logger.warning(f"Failed to capture snapshot for trace {trace_id}: {e}")
                # We proceed with logging the trace even if snapshot fails
                
        try:
            with self.postgres.get_session() as session:
                trace = DecisionTraceModel(
                    id=trace_id,
                    rule_id=rule_id,
                    trigger_event_id=trigger_event_id,
                    action_type=action_type,
                    input_payload=input_payload,
                    output_payload=output_payload,
                    status=status,
                    error_message=error_message,
                    latency_ms=latency_ms,
                    snapshot_id=snapshot_id,
                    timestamp=datetime.utcnow()
                )
                session.add(trace)
                session.commit()
                
            logger.info(f"Logged decision trace {trace_id} for action {action_type}")
            return trace_id
            
        except Exception as e:
            logger.error(f"Failed to log decision trace: {e}")
            raise
