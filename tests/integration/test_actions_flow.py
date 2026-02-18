import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import datetime

from orgmind.triggers.models import RuleModel, NotificationModel
from orgmind.triggers.repository import RuleRepository
from orgmind.triggers.actions.registry import ActionRegistry, init_actions
from orgmind.triggers.engine.worker import RuleExecutor
from orgmind.events import Event, EventType
from orgmind.storage.models import Base

# Setup DB
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

@pytest.fixture
def rule_repo(db_session):
    return RuleRepository()

@pytest.mark.asyncio
async def test_action_integration_flow(db_session, rule_repo):
    # 1. Setup Rules
    # Rule 1: Slack
    rule_slack = RuleModel(
        id="rule_slack",
        name="Slack Rule",
        event_type_filter="object.created",
        condition={"==": [{"var": "type"}, "bug"]},
        action_config={
            "type": "slack", 
            "webhook_url": "http://slack.local",
            "message": "Bug created: {{ rule_name }}"
        },
        enabled=True
    )
    
    # Rule 2: In App
    rule_in_app = RuleModel(
        id="rule_in_app",
        name="InApp Rule",
        event_type_filter="object.created",
        condition={"==": [{"var": "priority"}, "high"]},
        action_config={
            "type": "in_app",
            "title": "High Priority",
            "message": "Check this out"
        },
        enabled=True
    )
    
    rule_repo.create(db_session, rule_slack)
    rule_repo.create(db_session, rule_in_app)
    
    # 2. Init Actions (registers handlers)
    # Ensure our actions are registered
    init_actions()
    
    # 3. Setup Executor with mocks
    mock_bus = AsyncMock()
    mock_db_adapter = Mock()
    session_cm = Mock()
    session_cm.__enter__ = Mock(return_value=db_session)
    session_cm.__exit__ = Mock(return_value=None)
    mock_db_adapter.get_session.return_value = session_cm
    
    executor = RuleExecutor(mock_bus, mock_db_adapter)
    executor.running = True
    
    # 4. Mock HTTPX for Slack
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client_instance
        
        response = Mock()
        response.status_code = 200
        response.raise_for_status = Mock()
        mock_client_instance.post.return_value = response
        
        # 5. Trigger Event
        
        event = Event(
            event_id=uuid4(),
            event_type=EventType.OBJECT_CREATED,
            entity_id=uuid4(),
            entity_type="object",
            tenant_id=uuid4(), # Use uuid for tenant_id as it might be expected
            timestamp=datetime.utcnow(),
            payload={
                "id": "obj-1", 
                "type": "bug", 
                "priority": "high",
                "name": "Critical bug"
            }
        )
        
        # Convert tenant_id to string for assertions if needed
        tenant_id_str = str(event.tenant_id)
        
        await executor.handle_event(event)
        
        # 6. Verify Slack Action
        mock_client_instance.post.assert_called_once()
        args, kwargs = mock_client_instance.post.call_args
        assert args[0] == "http://slack.local"
        assert "Bug created: Slack Rule" in kwargs["json"]["text"]
        
        # 7. Verify InApp Action
        # Check DB
        notifications = db_session.query(NotificationModel).all()
        assert len(notifications) == 1
        notif = notifications[0]
        assert notif.rule_name == "InApp Rule"
        assert notif.tenant_id == tenant_id_str
        assert notif.title == "High Priority"
