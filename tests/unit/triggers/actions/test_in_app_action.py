import pytest
import logging
from unittest.mock import Mock, MagicMock
from orgmind.triggers.actions.in_app_action import InAppNotificationAction
from orgmind.triggers.actions.base import ActionContext
from orgmind.triggers.models import NotificationModel

@pytest.mark.asyncio
async def test_in_app_action_success():
    action = InAppNotificationAction()
    mock_session = MagicMock()
    
    context = ActionContext(
        event_type="test_event",
        event_data={"key": "value"},
        rule_name="Test Rule",
        tenant_id="tenant-1",
        session=mock_session
    )
    
    config = {
        "title": "Title for {{ rule_name }}",
        "message": "Message for {{ event_type }}"
    }
    
    await action.execute(config, context)
    
    mock_session.add.assert_called_once()
    # Check the argument passed to add
    args, _ = mock_session.add.call_args
    notification = args[0]
    
    assert isinstance(notification, NotificationModel)
    assert notification.tenant_id == "tenant-1"
    assert notification.title == "Title for Test Rule"
    assert notification.message == "Message for test_event"
    assert notification.data["event_data"] == {"key": "value"}
    assert notification.rule_name == "Test Rule"

@pytest.mark.asyncio
async def test_in_app_action_missing_context(caplog):
    action = InAppNotificationAction()
    context = ActionContext(event_type="t", event_data={}, rule_name="r")
    
    # Test missing session
    with caplog.at_level(logging.ERROR):
        await action.execute({}, context)
    assert "No DB session" in caplog.text
    
    caplog.clear()
    
    # Test missing tenant_id
    mock_session = MagicMock()
    context.session = mock_session
    
    with caplog.at_level(logging.ERROR):
        await action.execute({}, context)
    assert "No tenant_id" in caplog.text
