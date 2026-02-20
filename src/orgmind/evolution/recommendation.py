from typing import List, Dict, Any
from sqlalchemy.orm import Session

from orgmind.evolution.embedding import DecisionEmbeddingService
from orgmind.evolution.policy import PolicyGenerator

class RecommendationEngine:
    """
    Suggests the best course of action based on:
    1. Similar past successful decisions (Precedents)
    2. Active policies (Rules)
    """
    
    def __init__(
        self, 
        embedding_service: DecisionEmbeddingService,
        policy_generator: PolicyGenerator
    ):
        self.embedding_service = embedding_service
        self.policy_generator = policy_generator

    async def recommend_action(
        self, 
        session: Session,
        current_context: Dict[str, Any],
        context_text: str
    ) -> List[Dict[str, Any]]:
        
        recommendations = []
        
        # 1. Check Policies (Hard constraints or Warnings)
        active_policies = self.policy_generator.evaluate_policies(session, current_context)
        
        warnings = []
        for policy in active_policies:
            if policy.effect == "DENY":
                return [{"type": "DENY", "reason": policy.message}]
            elif policy.effect == "WARN":
                warnings.append(policy.message)
                
        # 2. Find Similar Successes (Soft guidance)
        similar_decisions = await self.embedding_service.search_similar(
            current_context_text=context_text,
            limit=5,
            msg_filter={"status": "success"} # Only want successful precedents
        )
        
        for decision in similar_decisions:
             recommendations.append({
                 "type": "PRECEDENT",
                 "action": decision.payload.get("action_type"),
                 "score": decision.score,
                 "reason": f"Similar to successful decision {decision.id}"
             })
             
        # Add policy warnings to response
        if warnings:
            recommendations.insert(0, {"type": "WARNING", "messages": warnings})
            
        return recommendations
