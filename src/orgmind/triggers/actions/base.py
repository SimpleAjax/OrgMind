from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from sqlalchemy.orm import Session
import logging

class ActionContext:
    """
    Context passed to an action execution.
    Contains the event payload, rule definition, etc.
    """
    def __init__(self, event_type: str, event_data: Dict[str, Any], rule_name: str, 
                 tenant_id: str = None, session: Session = None):
        self.event_type = event_type
        self.event_data = event_data
        self.rule_name = rule_name
        self.tenant_id = tenant_id
        self.session = session
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_data": self.event_data,
            "rule_name": self.rule_name,
            "tenant_id": self.tenant_id,
        }

class Action(ABC):
    """
    Base class for automation actions triggered by rules.
    """
    
    @property
    @abstractmethod
    def type_name(self) -> str:
        """The identifier for this action type (e.g., 'slack', 'log')."""
        pass
        
    @abstractmethod
    async def execute(self, config: Dict[str, Any], context: ActionContext) -> None:
        """
        Execute the action.
        
        Args:
            config: The action configuration from the rule (e.g. channel ID, message template)
            context: The triggering event and context
        """
        pass
