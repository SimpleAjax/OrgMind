import logging
from typing import Dict, Any, Optional
from uuid import uuid4
from datetime import datetime
from .base import Action, ActionContext
from orgmind.triggers.models import NotificationModel

logger = logging.getLogger(__name__)

class InAppNotificationAction(Action):
    """
    Creates a notification record in the database.
    """
    
    @property
    def type_name(self) -> str:
        return "in_app"

    async def execute(self, config: Dict[str, Any], context: ActionContext) -> None:
        if not context.session:
            logger.error(f"No DB session in context for InAppNotificationAction rule '{context.rule_name}'")
            return
            
        if not context.tenant_id:
            logger.error(f"No tenant_id in context for InAppNotificationAction rule '{context.rule_name}'")
            return
            
        title_template = config.get("title", "Notification: {{ rule_name }}")
        message_template = config.get("message", "Event triggered: {{ event_type }}")
        
        # Templating
        title = title_template.replace("{{ rule_name }}", context.rule_name) \
                              .replace("{{ event_type }}", context.event_type)
        message = message_template.replace("{{ rule_name }}", context.rule_name) \
                                  .replace("{{ event_type }}", context.event_type)
                                  
        for key, value in context.event_data.items():
            if isinstance(value, (str, int, float, bool)):
                 title = title.replace(f"{{{{ {key} }}}}", str(value))
                 message = message.replace(f"{{{{ {key} }}}}", str(value))
        
        notification = NotificationModel(
            id=str(uuid4()),
            tenant_id=context.tenant_id,
            rule_name=context.rule_name,
            title=title,
            message=message,
            data={"event_data": context.event_data},
            created_at=datetime.utcnow()
        )
        
        try:
            context.session.add(notification)
            logger.info(f"InApp notification created for rule '{context.rule_name}'")
        except Exception as e:
            logger.error(f"Failed to create InApp notification: {e}")
