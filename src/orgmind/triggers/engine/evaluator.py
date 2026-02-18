import logging
from typing import Dict, Any, List, Union
import json_logic
from datetime import datetime

logger = logging.getLogger(__name__)

class ConditionEvaluator:
    """
    Evaluates JSONLogic conditions against event data.
    """
    
    def __init__(self):
        # We can add custom operations here if needed
        # e.g. json_logic.add_operation("date_diff", date_diff)
        pass

    def evaluate(self, condition: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """
        Evaluate a JSONLogic rule against the provided data.
        
        Args:
            condition: The JSONLogic rule (e.g. {"==": [{"var": "status"}, "active"]})
            data: The context data to evaluate against (e.g. {"status": "active", ...})
            
        Returns:
            bool: True if condition matches, False otherwise.
        """
        try:
            # json_logic.jsonLogic returns the result of the evaluation
            # For a condition, we expect a boolean result.
            result = json_logic.jsonLogic(condition, data)
            
            # Ensure we return a boolean
            return bool(result)
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}", exc_info=True)
            # Default to False on error to be safe? Or maybe we want to know?
            # For now, safe default is False (rule doesn't match).
            return False

    def validate_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Validate if a condition structure is valid JSONLogic.
        # json_logic python lib doesn't seem to have a strict validator, 
        # but we can try a dry run with empty data or checks.
        """
        if not isinstance(condition, dict):
            return False
            
        # Basic check: should have operators as keys
        # We can try a simple evaluation to see if it crashes
        try:
            json_logic.jsonLogic(condition, {})
            return True
        except Exception:
            return False
