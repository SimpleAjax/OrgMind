import logging
import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from orgmind.storage.models_traces import DecisionTraceModel
from orgmind.storage.models_context import ContextEventModel, ContextLinkModel
from orgmind.storage.postgres_adapter import PostgresAdapter

logger = logging.getLogger(__name__)

class CorrelationEngine:
    def process_correlations(self, postgres: PostgresAdapter):
        """
        Main loop: Find traces without context links and try to link them to events.
        """
        logger.info("Running Correlation Engine check...")
        
        with postgres.get_session() as session:
            # 1. Find recent traces (last 1 hour)
            # Optimization: Only those without links? 
            # For simplicity in MVP, we re-check recent 1h traces. 
            # To avoid duplicates, we check existing links before creating.
            
            now = datetime.utcnow()
            window_start = now - timedelta(hours=1)
            
            # Get traces
            traces = session.query(DecisionTraceModel).filter(
                DecisionTraceModel.timestamp >= window_start
            ).all()
            
            for trace in traces:
                self._correlate_trace(session, trace)

    def _correlate_trace(self, session: Session, trace: DecisionTraceModel):
        # Time window: +/- 5 minutes
        start_time = trace.timestamp - timedelta(minutes=5)
        end_time = trace.timestamp + timedelta(minutes=5)
        
        # Find context events in this window matching user
        query = session.query(ContextEventModel).filter(
            ContextEventModel.timestamp >= start_time,
            ContextEventModel.timestamp <= end_time
        )
        
        if trace.user_id:
             query = query.filter(ContextEventModel.user_id == trace.user_id)
        
        # Also maybe match session_id if we have it on trace? (Not yet)
        
        events = query.all()
        
        links_created = 0
        for event in events:
            # Check if link exists
            exists = session.query(ContextLinkModel).filter_by(
                trace_id=trace.id,
                context_event_id=event.id
            ).first()
            
            if not exists:
                link = ContextLinkModel(
                    id=str(uuid.uuid4()),
                    trace_id=trace.id,
                    context_event_id=event.id,
                    link_type="temporal",
                    relevance_score=1.0 # Simple temporal match
                )
                session.add(link)
                links_created += 1
        
        if links_created > 0:
            session.commit()
            logger.info(f"Created {links_created} context links for trace {trace.id}")
