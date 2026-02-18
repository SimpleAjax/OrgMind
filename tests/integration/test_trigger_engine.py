import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from orgmind.triggers.engine.worker import RuleExecutor
from orgmind.triggers.models import RuleModel
from orgmind.triggers.repository import RuleRepository
from orgmind.events import Event, EventType
from orgmind.triggers.actions.registry import ActionRegistry
from orgmind.triggers.actions.base import Action, ActionContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from orgmind.storage.models import Base

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()

# Create a mock action to verify execution
class MockAction(Action):
    def __init__(self):
        self.executed = False
        self.last_context = None
        self.last_config = None
        
    @property
    def type_name(self) -> str:
        return "mock"
        
    async def execute(self, config: dict, context: ActionContext) -> None:
        self.executed = True
        self.last_context = context
        self.last_config = config

@pytest.fixture
def mock_action():
    return MockAction()

@pytest.fixture
def rule_repo(db_session):
    return RuleRepository()

@pytest.mark.asyncio
async def test_rule_execution_flow(db_session, rule_repo, mock_action):
    # 1. Setup Rule
    rule = RuleModel(
        id="rule_test_trigger",
        name="Test Trigger Rule",
        event_type_filter="object.created",  # Match EventType value
        condition={"==": [{"var": "status"}, "active"]},
        action_config={"type": "mock", "message": "hello"},
        enabled=True
    )
    rule_repo.create(db_session, rule)
    
    # 2. Register Mock Action
    ActionRegistry.register(mock_action)
    
    # 3. Setup Executor with mocked dependencies
    mock_bus = AsyncMock()
    mock_db_adapter = Mock()
    # Configure mock for context manager
    session_cm = Mock()
    session_cm.__enter__ = Mock(return_value=db_session)
    session_cm.__exit__ = Mock(return_value=None)
    mock_db_adapter.get_session.return_value = session_cm
    
    executor = RuleExecutor(mock_bus, mock_db_adapter)
    executor.running = True
    
    # 4. Trigger Event
    from uuid import uuid4
    from datetime import datetime
    
    event = Event(
        event_id=uuid4(),
        event_type=EventType.OBJECT_CREATED,
        entity_id=uuid4(),
        entity_type="object",
        tenant_id=uuid4(),
        timestamp=datetime.utcnow(),
        payload={"id": "obj-1", "status": "active", "name": "Test Object"}
    )
    
    # 5. Execute
    await executor.handle_event(event)
    
    # 6. Verify
    assert mock_action.executed is True
    assert mock_action.last_context.rule_name == "Test Trigger Rule"
    assert mock_action.last_context.event_data["id"] == "obj-1"

@pytest.mark.asyncio
async def test_rule_condition_mismatch(db_session, rule_repo, mock_action):
    # Rule expects status='active'
    rule = RuleModel(
        id="rule_mismatch",
        name="Mismatch Rule",
        event_type_filter="object.created",
        condition={"==": [{"var": "status"}, "active"]},
        action_config={"type": "mock"},
        enabled=True
    )
    rule_repo.create(db_session, rule)
    ActionRegistry.register(mock_action)
    
    mock_bus = AsyncMock()
    mock_db_adapter = Mock()
    session_cm = Mock()
    session_cm.__enter__ = Mock(return_value=db_session)
    session_cm.__exit__ = Mock(return_value=None)
    mock_db_adapter.get_session.return_value = session_cm
    
    executor = RuleExecutor(mock_bus, mock_db_adapter)
    executor.running = True
    
    # Event has status='draft' -> Should NOT trigger
    from uuid import uuid4
    from datetime import datetime
    
    event = Event(
        event_id=uuid4(),
        event_type=EventType.OBJECT_CREATED,
        entity_id=uuid4(),
        entity_type="object",
        tenant_id=uuid4(),
        timestamp=datetime.utcnow(),
        payload={"id": "obj-2", "status": "draft"}
    )
    
    await executor.handle_event(event)
    
    assert mock_action.executed is False
