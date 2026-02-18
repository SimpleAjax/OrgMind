import logging
import json
from .base import Action, ActionContext

logger = logging.getLogger(__name__)

class LogAction(Action):
    """
    Simple action that logs the trigger to application logs.
    Useful for testing rules.
    """
    
    @property
    def type_name(self) -> str:
        return "log"

    async def execute(self, config: dict, context: ActionContext) -> None:
        level = config.get("level", "INFO").upper()
        message = config.get("message", "Rule triggered: {{ rule_name }} for {{ event_type }}")
        
        # Simple string formatting (could be extended to proper templating)
        try:
            formatted_message = message.replace("{{ rule_name }}", context.rule_name) \
                                        .replace("{{ event_type }}", context.event_type)
            # Add basic object id support if present
            if "id" in context.event_data:
                formatted_message = formatted_message.replace("{{ object.id }}", str(context.event_data.get("id")))
                
            log_fn = getattr(logger, level.lower(), logger.info)
            log_fn(f"[LogAction] {formatted_message} | Config: {json.dumps(config)} | Context: {context.event_data}")
            
        except Exception as e:
            logger.error(f"Error executing LogAction for {context.rule_name}: {e}")
