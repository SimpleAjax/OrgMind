import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orgmind.storage.models import Base
from orgmind.storage.models_traces import DecisionTraceModel, ContextSnapshotModel
from orgmind.triggers.models import RuleModel
from orgmind.triggers.engine.worker import RuleExecutor
from orgmind.triggers.repository import RuleRepository
from orgmind.events import Event
from orgmind.triggers.actions.registry import ActionRegistry
from orgmind.triggers.actions.base import Action, ActionContext

# --- Fixtures ---

@pytest.fixture
def db_engine():
    # Use standard sqlite memory db
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Create all tables (including traces)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()

class MockAction(Action):
    def __init__(self):
        self.executed = False
        
    @property
    def type_name(self) -> str:
        return "trace_test_mock" # Validated in registry
        
    async def execute(self, config: dict, context: ActionContext) -> None:
        self.executed = True

@pytest.fixture
def mock_action():
    return MockAction()

@pytest.mark.asyncio
async def test_decision_trace_creation(db_session, mock_action):
    # 1. Setup Data & Rules
    repo = RuleRepository()
    rule = RuleModel(
        id=str(uuid4()),
        name="Trace Test Rule",
        event_type_filter="object.updated",
        condition={"==": [{"var": "status"}, "active"]},
        action_config={"type": "trace_test_mock"},
        enabled=True
    )
    repo.create(db_session, rule)
    db_session.commit()
    
    # Register our mock action
    ActionRegistry.register(mock_action)
    
    # 2. Setup Executor Dependencies
    mock_bus = AsyncMock()
    
    # Mock Neo4j
    mock_neo4j = Mock()
    # verify_connectivity called in constructor? No, simpler.
    # We need execute_read to return something for snapshot
    mock_neo4j.execute_read.return_value = [{"nodes": [], "rels": []}] 
    
    # Mock Postgres Adapter to return our sqlite session
    mock_db_adapter = Mock()
    session_cm = Mock()
    session_cm.__enter__ = Mock(return_value=db_session)
    session_cm.__exit__ = Mock(return_value=None)
    mock_db_adapter.get_session.return_value = session_cm
    
    # 3. Initialize Executor
    executor = RuleExecutor(mock_bus, mock_db_adapter, neo4j_adapter=mock_neo4j)
    executor.running = True
    
    # 4. Trigger Event
    event_payload = {"id": "obj-trace-1", "status": "active"}
    event = Event(
        event_id=uuid4(),
        event_type="object.updated",
        entity_id=uuid4(),
        entity_type="object",
        tenant_id=uuid4(),
        timestamp=datetime.utcnow(),
        payload=event_payload
    )
    
    # 5. Handle Event
    # We call process_rules directly or handle_event. existing test calls handle_event.
    await executor.handle_event(event)
    
    # 6. Verify Action Execution
    assert mock_action.executed is True, "Action should have executed"
    
    # 7. Verify Traces in DB
    # We expect 2 traces:
    # A) Rule Evaluation (Success match)
    # B) Action Execution (Success)
    
    traces = db_session.query(DecisionTraceModel).all()
    assert len(traces) >= 2, f"Expected at least 2 traces, found {len(traces)}"
    
    eval_traces = [t for t in traces if t.action_type == "rule_evaluation"]
    action_traces = [t for t in traces if t.action_type == "trace_test_mock"]
    
    assert len(eval_traces) == 1
    assert eval_traces[0].output_payload["match"] is True
    assert eval_traces[0].rule_id == rule.id
    
    assert len(action_traces) == 1
    assert action_traces[0].status == "success"
    assert action_traces[0].rule_id == rule.id
    
    # 8. Verify Snapshot
    # Action execution should capture snapshot because payload has 'id'
    snapshot_id = action_traces[0].snapshot_id
    assert snapshot_id is not None
    
    snapshot = db_session.query(ContextSnapshotModel).filter_by(id=snapshot_id).first()
    assert snapshot is not None
    
