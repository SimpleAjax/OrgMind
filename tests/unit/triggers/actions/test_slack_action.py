import pytest
import logging
from unittest.mock import AsyncMock, Mock, patch
from orgmind.triggers.actions.slack_action import SlackNotificationAction
from orgmind.triggers.actions.base import ActionContext

@pytest.mark.asyncio
async def test_slack_action_success():
    action = SlackNotificationAction()
    context = ActionContext(
        event_type="test_event",
        event_data={"key": "value", "id": 123},
        rule_name="Test Rule"
    )
    
    # Mock httpx.AsyncClient context manager
    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client_instance
        
        response = Mock()
        response.raise_for_status = Mock()
        mock_client_instance.post.return_value = response
        
        config = {
            "webhook_url": "http://slack.com/webhook",
            "message": "Alert: {{ rule_name }} for item {{ id }}"
        }
        
        await action.execute(config, context)
        
        mock_client_instance.post.assert_called_once()
        args, kwargs = mock_client_instance.post.call_args
        assert args[0] == "http://slack.com/webhook"
        assert kwargs["json"]["text"] == "Alert: Test Rule for item 123"

@pytest.mark.asyncio
async def test_slack_action_missing_url(caplog):
    action = SlackNotificationAction()
    context = ActionContext(event_type="t", event_data={}, rule_name="r")
    
    with caplog.at_level(logging.ERROR):
        await action.execute({}, context)
    
    assert "Slack webhook_url missing" in caplog.text
