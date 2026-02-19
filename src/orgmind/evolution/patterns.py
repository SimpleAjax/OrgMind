from typing import Dict, Any, List
from sqlalchemy import select, func, desc
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.evolution.models import OutcomeEventModel, ScheduledOutcomeModel, OutcomeDefinitionModel

class PatternDetector:
    """
    Analyzes outcome data to find patterns of success or failure.
    """
    
    def __init__(self, db_adapter: PostgresAdapter):
        self.db = db_adapter

    async def analyze_definition(self, definition_id: str) -> Dict[str, Any]:
        """
        Analyze success rates for a specific outcome definition.
        """
        with self.db.get_session() as session:
            # Basic stats: Avg Score, Count
            stmt = select(
                func.count(OutcomeEventModel.id).label("count"),
                func.avg(OutcomeEventModel.score).label("avg_score")
            ).join(
                ScheduledOutcomeModel, OutcomeEventModel.scheduled_outcome_id == ScheduledOutcomeModel.id
            ).where(
                ScheduledOutcomeModel.definition_id == definition_id
            )
            
            result = session.execute(stmt).first()
            count = result.count or 0
            avg_score = result.avg_score or 0.0
            
            # Find top performing contexts? 
            # This requires linking back to DecisionTrace and its context.
            # For MVP, we just return the aggregate.
            
            return {
                "definition_id": definition_id,
                "total_events": count,
                "average_score": float(avg_score),
                "analysis_timestamp": func.now()
            }

    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Find definitions with unusually low success rates.
        """
        anomalies = []
        with self.db.get_session() as session:
            # Get all definitions
            definitions = session.scalars(select(OutcomeDefinitionModel)).all()
            
            for definition in definitions:
                stats = await self.analyze_definition(definition.id)
                if stats["total_events"] > 5 and stats["average_score"] < 0.5:
                    anomalies.append({
                        "type": "low_success_rate",
                        "definition": definition.name,
                        "stats": stats
                    })
                    
        return anomalies
