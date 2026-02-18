import logging
from typing import Dict, Any
import httpx
from .base import Action, ActionContext

logger = logging.getLogger(__name__)

class SlackNotificationAction(Action):
    """
    Sends a notification to Slack via a webhook URL.
    """
    
    @property
    def type_name(self) -> str:
        return "slack"

    async def execute(self, config: Dict[str, Any], context: ActionContext) -> None:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.error(f"Slack webhook_url missing for rule '{context.rule_name}'")
            return
            
        message_template = config.get("message", "Rule triggered: {{ rule_name }}")
        
        # Simple templating
        message = message_template.replace("{{ rule_name }}", context.rule_name) \
                                  .replace("{{ event_type }}", context.event_type)
        
        # Add payload data to template if needed (primitive types only for now)
        for key, value in context.event_data.items():
            if isinstance(value, (str, int, float, bool)):
                 message = message.replace(f"{{{{ {key} }}}}", str(value))
        
        payload = {"text": message}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Slack notification sent for rule '{context.rule_name}'")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack notification for '{context.rule_name}': {e}")
