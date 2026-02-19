from datetime import datetime, timedelta
import logging
from typing import List, Optional, Type
from sqlalchemy import select, and_
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.evolution.models import (
    ScheduledOutcomeModel, OutcomeDefinitionModel, OutcomeEventModel, 
    ScheduledOutcomeStatus
)
from orgmind.evolution.collectors import (
    MetricCollector, TaskCompletionCollector, EmailReplyCollector, MockCollector
)
from orgmind.evolution.scoring import SuccessScoringEngine

logger = logging.getLogger(__name__)

class OutcomeScheduler:
    """
    Manages the scheduling and execution of outcome checks.
    """
    
    def __init__(self, db_adapter: PostgresAdapter):
        self.db = db_adapter
        self.scoring_engine = SuccessScoringEngine()
        self.collectors = {
            "task_completion": TaskCompletionCollector(),
            "email_reply": EmailReplyCollector(),
            "mock": MockCollector(),
        }

    async def schedule_check(
        self, 
        trace_id: str, 
        definition_id: str, 
        delay_minutes: int = 60
    ) -> str:
        """
        Schedule a new outcome check for a decision trace.
        """
        import uuid
        scheduled_id = str(uuid.uuid4())
        scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
        
        with self.db.get_session() as session:
            # check if definition exists
            definition = session.get(OutcomeDefinitionModel, definition_id)
            if not definition:
                raise ValueError(f"OutcomeDefinition {definition_id} not found")
                
            scheduled = ScheduledOutcomeModel(
                id=scheduled_id,
                trace_id=trace_id,
                definition_id=definition_id,
                scheduled_at=scheduled_at,
                next_attempt_at=scheduled_at,
                status=ScheduledOutcomeStatus.PENDING
            )
            session.add(scheduled)
            session.commit()
            logger.info(f"Scheduled outcome check {scheduled_id} for trace {trace_id} at {scheduled_at}")
            return scheduled_id

    async def run_due_checks(self, limit: int = 10):
        """
        Fetch due checks and run them.
        """
        now = datetime.utcnow()
        
        # We need to process one by one or in batches, managing sessions carefully
        # Here we fetch IDs first to avoid long-held locks or complex session sharing if we go async
        due_ids = []
        with self.db.get_session() as session:
            stmt = select(ScheduledOutcomeModel.id).where(
                and_(
                    ScheduledOutcomeModel.status == ScheduledOutcomeStatus.PENDING,
                    ScheduledOutcomeModel.next_attempt_at <= now
                )
            ).limit(limit)
            due_ids = session.scalars(stmt).all()
            
        logger.info(f"Found {len(due_ids)} due outcome checks")
        
        for outcome_id in due_ids:
            try:
                await self._process_outcome(outcome_id)
            except Exception as e:
                logger.exception(f"Error processing outcome {outcome_id}: {e}")

    async def _process_outcome(self, outcome_id: str):
        """
        Execute a single outcome check.
        """
        with self.db.get_session() as session:
            scheduled = session.get(ScheduledOutcomeModel, outcome_id)
            if not scheduled or scheduled.status != ScheduledOutcomeStatus.PENDING:
                return

            definition = scheduled.definition
            collector = self.collectors.get(definition.collector_type)
            
            if not collector:
                logger.error(f"No collector found for type {definition.collector_type}")
                scheduled.status = ScheduledOutcomeStatus.FAILED
                scheduled.last_error = f"Unknown collector type: {definition.collector_type}"
                session.commit()
                return

            # Prepare context (in a real scenario, we'd fetch this from the Trace/Graph)
            # For now, we assume context is derivable or stored (maybe we need to link context events)
            # Simplification: pass empty context or minimal ID context
            context = {"trace_id": scheduled.trace_id}
            
            # Update attempt count
            scheduled.attempts += 1
            scheduled.last_attempt_at = datetime.utcnow()
            
            try:
                # 1. Collect Metrics
                metrics = await collector.collect(definition.parameters, context)
                
                # 2. Compute Score
                score = self.scoring_engine.calculate_score(metrics, definition.parameters)
                
                # 3. Record Event
                import uuid
                event = OutcomeEventModel(
                    id=str(uuid.uuid4()),
                    scheduled_outcome_id=outcome_id,
                    metrics=metrics,
                    score=score,
                    timestamp=datetime.utcnow()
                )
                session.add(event)
                
                # 4. Determine Status
                # Simplification: If we got a result, we mark as completed.
                # In reality, we might retry if "reply not yet received" but timeout hasn't passed.
                # For this MVP, we mark COMPLETED.
                scheduled.status = ScheduledOutcomeStatus.COMPLETED
                
                logger.info(f"Outcome check {outcome_id} completed. Score: {score}")
                
            except Exception as e:
                logger.exception(f"Collector failed for {outcome_id}")
                # Retry logic could go here (exp backoff)
                scheduled.next_attempt_at = datetime.utcnow() + timedelta(minutes=10)
                
            session.commit()
