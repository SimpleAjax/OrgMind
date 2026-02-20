from typing import List, Dict, Any, Optional
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from orgmind.evolution.models import EvolutionPolicyModel
from orgmind.triggers.engine import JsonLogicEvaluator # Reusing existing evaluator

logger = logging.getLogger(__name__)

class PolicyGenerator:
    """
    Generates new policies from detected patterns and evaluates existing policies against context.
    """
    
    def __init__(self, evaluator: JsonLogicEvaluator):
        self.evaluator = evaluator

    def generate_policy_from_pattern(self, pattern: Dict[str, Any]) -> EvolutionPolicyModel:
        """
        Converts a detected pattern (e.g. "Fridays have high failure rate for X") 
        into a formal policy candidate.
        """
        # Example pattern: { "feature": "day_of_week", "value": "Friday", "outcome_score": 0.2 }
        
        condition = {
            "==": [{"var": "context.day_of_week"}, "Friday"]
        }
        
        policy = EvolutionPolicyModel(
            name=f"Avoid actions on Friday due to low success",
            description="Generated from pattern detection #123",
            condition_logic=condition,
            effect="WARN",
            message="Historical data suggests high failure rates on Fridays.",
            source="pattern_detection_service",
            confidence=0.8
        )
        return policy

    def evaluate_policies(
        self, 
        session: Session, 
        context: Dict[str, Any]
    ) -> List[EvolutionPolicyModel]:
        """
        Returns a list of active policies that match the current context.
        """
        active_policies = session.scalars(
            select(EvolutionPolicyModel).where(EvolutionPolicyModel.is_active == True)
        ).all()
        
        applicable_policies = []
        for policy in active_policies:
            try:
                if self.evaluator.evaluate(policy.condition_logic, context):
                    applicable_policies.append(policy)
            except Exception as e:
                logger.error(f"Failed to evaluate policy {policy.id}: {e}")
                
        return applicable_policies
