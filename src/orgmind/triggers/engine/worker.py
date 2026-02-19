import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from contextlib import contextmanager

from orgmind.events import NatsEventBus, Event
from orgmind.triggers.models import RuleModel
from orgmind.triggers.repository import RuleRepository
from orgmind.triggers.engine.evaluator import ConditionEvaluator
from orgmind.triggers.actions.registry import ActionRegistry, init_actions
from orgmind.triggers.actions.base import ActionContext
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.graph.neo4j_adapter import Neo4jAdapter
from orgmind.engine.context_capture import ContextSnapshotService
from orgmind.engine.decision_tracer import DecisionTraceService

logger = logging.getLogger(__name__)

class RuleExecutor:
    """
    Subscribes to events and executes matching rules.
    """
    
    def __init__(self, event_bus: NatsEventBus, db_adapter: PostgresAdapter, neo4j_adapter: Optional[Neo4jAdapter] = None):
        self.bus = event_bus
        self.db = db_adapter
        self.neo4j = neo4j_adapter or Neo4jAdapter() # Default connection if not provided
        self.evaluator = ConditionEvaluator()
        
        # Initialize trace services
        self.snapshot_service = ContextSnapshotService(self.db, self.neo4j)
        self.decision_tracer = DecisionTraceService(self.db, self.snapshot_service)
        
        # Connect to Neo4j if needed (lazy connection handled by adapter usually, but good to explicit)
        # self.neo4j.connect() # Might be handled by caller
        
        # Initialize actions
        init_actions()
        
        self.running = False

    async def start(self):
        """Start listening for events."""
        self.running = True
        logger.info("Starting Rule Executor...")
        
        # Subscribe to object events
        # Note: We might want separate handlers for different domains later
        await self.bus.subscribe("orgmind.object.>", self.handle_event)
        await self.bus.subscribe("orgmind.link.>", self.handle_event)
        
        logger.info("Rule Executor listening on orgmind.object.> and orgmind.link.>")

    async def handle_event(self, event: Event):
        """Process incoming event."""
        if not self.running:
            return

        # Handle both Enum and string event types safely
        event_type = event.event_type
        if hasattr(event_type, 'value'):
            event_type = event_type.value
        event_type = str(event_type)
        
        logger.debug(f"Handling event: {event.event_id} type: {event_type}")
        
        try:
            # We need a new DB session for each event to ensure fresh data and transaction isolation
            # The adapter provides context manager for session
            with self.db.get_session() as session:
                await self.process_rules(session, event, event_type)
                
        except Exception as e:
            logger.error(f"Error processing rules for event {event.event_id}: {e}", exc_info=True)

    async def process_rules(self, session: Session, event: Event, event_type_str: str):
        """Find and execute rules for the event.
        Args:
            session: DB Session
            event: The Event object
            event_type_str: The string representation of event type (e.g. 'object.created')
        """
        repo = RuleRepository()
        
        # event_type_str passed from handle_event
        
        rules = repo.list_by_event_type(session, event_type_str)
        logger.debug(f"Querying rules for event_type='{event_type_str}'. Found: {len(rules)}")
        if not rules:
            return
        
        # 2. Evaluate each rule
        # We construct the context data from the event payload
        # Usually event.payload contains the object data
        context_data = event.payload
        
        # We might want to flatten or enrich context_data?
        # For now, pass payload as is.
        
        for rule in rules:
            try:
                # Measure evaluation time
                start_eval = asyncio.get_event_loop().time()
                is_match = self.evaluator.evaluate(rule.condition, context_data)
                latency_eval = (asyncio.get_event_loop().time() - start_eval) * 1000
                
                # Log evaluation trace
                try:
                    self.decision_tracer.log_decision(
                        action_type="rule_evaluation",
                        input_payload={
                            "rule_name": rule.name, 
                            "condition": rule.condition
                            # Avoid logging full data if huge, but helpful for debugging
                        },
                        output_payload={"match": is_match},
                        rule_id=rule.id,
                        trigger_event_id=str(event.event_id),
                        latency_ms=latency_eval,
                        status="success"
                    )
                except Exception as log_err:
                    logger.error(f"Failed to log rule evaluation: {log_err}")

                if is_match:
                    logger.info(f"Rule '{rule.name}' matched for event {event.event_id}")
                    await self.execute_action(session, rule, event, context_data)
                else:
                    logger.debug(f"Rule '{rule.name}' condition did not match.")
            except Exception as e:
                logger.error(f"Failed to evaluate/execute rule {rule.id}: {e}")
                # Log failure
                try:
                    self.decision_tracer.log_decision(
                        action_type="rule_evaluation",
                        input_payload={"rule_name": rule.name},
                        rule_id=rule.id,
                        trigger_event_id=str(event.event_id),
                        status="failure",
                        error_message=str(e)
                    )
                except Exception:
                    pass

    async def execute_action(self, session: Session, rule: RuleModel, event: Event, data: dict):
        """Execute the action defined in the rule."""
        action_config = rule.action_config
        action_type = action_config.get("type")
        
        # Prepare trace info
        trace_status = "success"
        error_msg = None
        start_time = asyncio.get_event_loop().time()
        
        if not action_type:
            logger.warning(f"Rule {rule.id} has no action type configured.")
            return

        try:
            handler = ActionRegistry.get(action_type)
            
            context = ActionContext(
                event_type=str(event.event_type),
                event_data=data,
                rule_name=rule.name,
                tenant_id=str(event.tenant_id),
                session=session
            )
            
            # Execute action
            await handler.execute(action_config, context)
            
        except ValueError as e:
            trace_status = "failure"
            error_msg = f"Action type '{action_type}' not found"
            logger.error(f"{error_msg} for rule {rule.id}")
        except Exception as e:
            trace_status = "failure"
            error_msg = str(e)
            logger.error(f"Action execution failed for rule {rule.id}: {e}", exc_info=True)
        finally:
            # Calculate latency
            end_time = asyncio.get_event_loop().time()
            latency_ms = (end_time - start_time) * 1000
            
            # Capture involved entities from event payload for snapshot
            # Assuming payload has 'id' or list of IDs relevant to event
            involved_ids = []
            if isinstance(data, dict):
                if 'id' in data:
                    involved_ids.append(data['id'])
                # Add logic to extract other IDs if needed based on event structure
            
            # Log trace
            try:
                self.decision_tracer.log_decision(
                    action_type=action_type,
                    input_payload=action_config,
                    # We don't easily capture output payload from void execute(), maybe update Action interface later
                    output_payload={"context_data_summary": list(data.keys())}, 
                    rule_id=rule.id,
                    trigger_event_id=str(event.event_id),
                    involved_entity_ids=involved_ids,
                    latency_ms=latency_ms,
                    status=trace_status,
                    error_message=error_msg
                )
            except Exception as e:
                logger.error(f"Failed to log decision trace: {e}")

    async def stop(self):
        self.running = False
        logger.info("Stopping Rule Executor...")
