from typing import Dict, Type
import logging
from .base import Action

logger = logging.getLogger(__name__)

class ActionRegistry:
    """
    Registry for available action types.
    """
    
    _actions: Dict[str, Action] = {}
    
    @classmethod
    def register(cls, action: Action) -> None:
        """Register an action handler."""
        # Simple singleton-esque registry, allowing multiple instances or types
        # For simplicity, we store instances
        name = action.type_name
        if name in cls._actions:
            logger.warning(f"Action type '{name}' already registered. Overwriting.")
        cls._actions[name] = action
        logger.info(f"Registered action handler for type: '{name}'")
        
    @classmethod
    def get(cls, type_name: str) -> Action:
        """Get an action handler by type."""
        handler = cls._actions.get(type_name)
        if not handler:
            raise ValueError(f"Action type '{type_name}' not found. Registered: {list(cls._actions.keys())}")
        return handler

# Helper to register default actions
# In real app, we might use entry_points or dependency injection
from .log_action import LogAction
from .slack_action import SlackNotificationAction
from .in_app_action import InAppNotificationAction

def init_actions():
    ActionRegistry.register(LogAction())
    ActionRegistry.register(SlackNotificationAction())
    ActionRegistry.register(InAppNotificationAction())
