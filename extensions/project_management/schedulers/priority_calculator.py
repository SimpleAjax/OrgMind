"""
Priority Calculator Scheduler

Calculates priority scores for projects based on multiple weighted factors:
- Customer tier (25%)
- Deadline proximity (25%)
- Business value (20%)
- Contract value (15%)
- Strategic importance (10%)
- Dependency boost (5%)
- Minus risk penalty

Usage:
    calculator = PriorityCalculator(db_adapter, neo4j_adapter)
    
    # Calculate single project
    score = await calculator.calculate_project_priority(project_id)
    
    # Batch recalculation
    await calculator.recalculate_all_priorities()
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import select, and_

from .base import SchedulerBase, ObjectModel, Session

logger = logging.getLogger(__name__)


@dataclass
class PriorityComponents:
    """Breakdown of priority score components."""
    customer_tier_score: float
    deadline_proximity_score: float
    business_value_score: float
    contract_value_score: float
    strategic_importance_score: float
    dependency_boost_score: float
    risk_penalty: float
    total_score: float


class PriorityCalculator(SchedulerBase):
    """
    Calculates priority scores for projects.
    
    Priority Score Formula:
    ```
    priority_score = (
        0.25 × customer_tier_score +
        0.25 × deadline_proximity_score +
        0.20 × business_value_score +
        0.15 × contract_value_score +
        0.10 × strategic_importance_score +
        0.05 × dependency_boost_score
    ) - risk_penalty
    ```
    """
    
    # Customer tier weights (higher tier = higher priority)
    CUSTOMER_TIER_WEIGHTS = {
        'tier_1': 100,  # Premium/VIP customers
        'tier_2': 75,   # Standard customers
        'tier_3': 50,   # Basic customers
    }
    
    # Weights for priority calculation (must sum to 1.0)
    WEIGHTS = {
        'customer_tier': 0.25,
        'deadline_proximity': 0.25,
        'business_value': 0.20,
        'contract_value': 0.15,
        'strategic_importance': 0.10,
        'dependency_boost': 0.05,
    }
    
    # Deadline scoring thresholds
    DEADLINE_URGENT_DAYS = 7      # Critical urgency
    DEADLINE_WARNING_DAYS = 30    # Warning threshold
    DEADLINE_PLANNING_DAYS = 90   # Normal planning horizon
    
    # Risk penalty per risk score point (risk_score 0-100)
    RISK_PENALTY_FACTOR = 0.3
    
    async def run(self, scope: str = "active_projects_only") -> Dict[str, Any]:
        """
        Run priority recalculation.
        
        Args:
            scope: "active_projects_only" or "all_projects"
            
        Returns:
            Summary of recalculation results
        """
        return await self.recalculate_all_priorities(scope)
    
    async def calculate_project_priority(
        self, 
        project_id: str,
        save: bool = True
    ) -> PriorityComponents:
        """
        Calculate priority score for a single project.
        
        Args:
            project_id: Project object ID
            save: Whether to save the score to the database
            
        Returns:
            PriorityComponents with score breakdown
        """
        with self.get_session() as session:
            project = self.get_object_by_id(session, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
                
            if project.type_id != 'ot_project':
                raise ValueError(f"Object {project_id} is not a project")
            
            components = self._calculate_components(session, project)
            
            if save:
                self.update_object_data(
                    session,
                    project_id,
                    {
                        'priority_score': round(components.total_score, 2),
                        'priority_calculated_at': self.now().isoformat(),
                        'priority_components': {
                            'customer_tier_score': round(components.customer_tier_score, 2),
                            'deadline_proximity_score': round(components.deadline_proximity_score, 2),
                            'business_value_score': round(components.business_value_score, 2),
                            'contract_value_score': round(components.contract_value_score, 2),
                            'strategic_importance_score': round(components.strategic_importance_score, 2),
                            'dependency_boost_score': round(components.dependency_boost_score, 2),
                            'risk_penalty': round(components.risk_penalty, 2),
                        }
                    }
                )
                session.commit()
                self.logger.info(
                    f"Updated priority for project {project_id}: "
                    f"score={components.total_score:.2f}"
                )
            
            return components
    
    async def recalculate_all_priorities(
        self,
        scope: str = "active_projects_only"
    ) -> Dict[str, Any]:
        """
        Recalculate priorities for all projects matching scope.
        
        Args:
            scope: "active_projects_only" or "all_projects"
            
        Returns:
            Summary dict with counts and statistics
        """
        with self.get_session() as session:
            # Get projects based on scope
            if scope == "active_projects_only":
                projects = self.get_objects_by_type(
                    session, 
                    'ot_project',
                    status='active'
                )
            else:
                projects = self.get_objects_by_type(session, 'ot_project')
            
            results = {
                'processed': 0,
                'updated': 0,
                'errors': 0,
                'scores': []
            }
            
            for project in projects:
                try:
                    components = self._calculate_components(session, project)
                    
                    self.update_object_data(
                        session,
                        project.id,
                        {
                            'priority_score': round(components.total_score, 2),
                            'priority_calculated_at': self.now().isoformat(),
                            'priority_components': {
                                'customer_tier_score': round(components.customer_tier_score, 2),
                                'deadline_proximity_score': round(components.deadline_proximity_score, 2),
                                'business_value_score': round(components.business_value_score, 2),
                                'contract_value_score': round(components.contract_value_score, 2),
                                'strategic_importance_score': round(components.strategic_importance_score, 2),
                                'dependency_boost_score': round(components.dependency_boost_score, 2),
                                'risk_penalty': round(components.risk_penalty, 2),
                            }
                        }
                    )
                    
                    results['updated'] += 1
                    results['scores'].append({
                        'project_id': project.id,
                        'project_name': project.data.get('name', 'Unknown'),
                        'score': components.total_score
                    })
                    
                except Exception as e:
                    self.logger.error(
                        f"Error calculating priority for project {project.id}: {e}"
                    )
                    results['errors'] += 1
                
                results['processed'] += 1
                
                # Commit every 10 projects to avoid long transactions
                if results['processed'] % 10 == 0:
                    session.commit()
            
            session.commit()
            
            # Calculate statistics
            if results['scores']:
                scores = [s['score'] for s in results['scores']]
                results['statistics'] = {
                    'min_score': min(scores),
                    'max_score': max(scores),
                    'avg_score': sum(scores) / len(scores)
                }
            
            self.logger.info(
                f"Priority recalculation complete: "
                f"{results['updated']} updated, {results['errors']} errors"
            )
            
            return results
    
    def get_priority_components(
        self,
        project_id: str
    ) -> Optional[PriorityComponents]:
        """
        Get priority components for a project without recalculating.
        
        Args:
            project_id: Project object ID
            
        Returns:
            PriorityComponents or None if not found
        """
        with self.get_session() as session:
            project = self.get_object_by_id(session, project_id)
            if not project:
                return None
                
            return self._calculate_components(session, project)
    
    def _calculate_components(
        self,
        session: Session,
        project: ObjectModel
    ) -> PriorityComponents:
        """
        Calculate all priority score components for a project.
        
        Args:
            session: Database session
            project: Project object
            
        Returns:
            PriorityComponents with all scores
        """
        data = project.data
        
        # 1. Customer Tier Score (25%)
        customer_tier_score = self._calculate_customer_tier_score(session, data)
        
        # 2. Deadline Proximity Score (25%)
        deadline_proximity_score = self._calculate_deadline_proximity_score(data)
        
        # 3. Business Value Score (20%)
        business_value_score = data.get('business_value_score', 50)
        
        # 4. Contract Value Score (15%)
        contract_value_score = self._calculate_contract_value_score(session, data)
        
        # 5. Strategic Importance Score (10%)
        strategic_importance_score = data.get('strategic_importance', 50)
        
        # 6. Dependency Boost Score (5%)
        dependency_boost_score = self._calculate_dependency_boost_score(
            session, project.id
        )
        
        # 7. Risk Penalty
        risk_penalty = self._calculate_risk_penalty(data)
        
        # Calculate total weighted score
        total_score = (
            self.WEIGHTS['customer_tier'] * customer_tier_score +
            self.WEIGHTS['deadline_proximity'] * deadline_proximity_score +
            self.WEIGHTS['business_value'] * business_value_score +
            self.WEIGHTS['contract_value'] * contract_value_score +
            self.WEIGHTS['strategic_importance'] * strategic_importance_score +
            self.WEIGHTS['dependency_boost'] * dependency_boost_score -
            risk_penalty
        )
        
        # Clamp to 0-100 range
        total_score = max(0.0, min(100.0, total_score))
        
        return PriorityComponents(
            customer_tier_score=round(customer_tier_score, 2),
            deadline_proximity_score=round(deadline_proximity_score, 2),
            business_value_score=round(business_value_score, 2),
            contract_value_score=round(contract_value_score, 2),
            strategic_importance_score=round(strategic_importance_score, 2),
            dependency_boost_score=round(dependency_boost_score, 2),
            risk_penalty=round(risk_penalty, 2),
            total_score=round(total_score, 2)
        )
    
    def _calculate_customer_tier_score(
        self,
        session: Session,
        project_data: Dict[str, Any]
    ) -> float:
        """Calculate score based on customer tier."""
        customer_id = project_data.get('customer_id')
        if not customer_id:
            return 50.0  # Default middle score
            
        customer = self.get_object_by_id(session, customer_id)
        if not customer:
            return 50.0
            
        tier = customer.data.get('tier', 'tier_2')
        return float(self.CUSTOMER_TIER_WEIGHTS.get(tier, 75))
    
    def _calculate_deadline_proximity_score(
        self,
        project_data: Dict[str, Any]
    ) -> float:
        """
        Calculate score based on how close the deadline is.
        
        Closer deadlines get higher priority scores.
        """
        planned_end = project_data.get('planned_end')
        if not planned_end:
            return 50.0  # Default if no deadline
            
        # Parse date if string
        if isinstance(planned_end, str):
            try:
                planned_end = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
            except ValueError:
                return 50.0
        
        days_until = self.days_until(planned_end)
        
        if days_until <= self.DEADLINE_URGENT_DAYS:
            return 100.0  # Critical urgency
        elif days_until <= self.DEADLINE_WARNING_DAYS:
            # Linear interpolation from 100 to 70
            progress = (days_until - self.DEADLINE_URGENT_DAYS) / \
                      (self.DEADLINE_WARNING_DAYS - self.DEADLINE_URGENT_DAYS)
            return 100.0 - (progress * 30.0)
        elif days_until <= self.DEADLINE_PLANNING_DAYS:
            # Linear interpolation from 70 to 40
            progress = (days_until - self.DEADLINE_WARNING_DAYS) / \
                      (self.DEADLINE_PLANNING_DAYS - self.DEADLINE_WARNING_DAYS)
            return 70.0 - (progress * 30.0)
        else:
            return 40.0  # Far future, lower priority
    
    def _calculate_contract_value_score(
        self,
        session: Session,
        project_data: Dict[str, Any]
    ) -> float:
        """
        Calculate score based on contract value relative to other projects.
        """
        contract_value = project_data.get('contract_value') or project_data.get('budget_amount', 0)
        if not contract_value:
            return 50.0
            
        # Get all project contract values for normalization
        # This is a simplified approach - in production, cache these values
        with self.get_session() as s:
            projects = self.get_objects_by_type(s, 'ot_project', limit=1000)
            values = [
                p.data.get('contract_value') or p.data.get('budget_amount', 0)
                for p in projects
                if (p.data.get('contract_value') or p.data.get('budget_amount', 0)) > 0
            ]
            
            if not values:
                return 50.0
                
            min_val = min(values)
            max_val = max(values)
            
            return self.normalize_score(contract_value, min_val, max_val)
    
    def _calculate_dependency_boost_score(
        self,
        session: Session,
        project_id: str
    ) -> float:
        """
        Calculate boost for projects that other projects depend on.
        
        Projects with more dependents get a small boost.
        """
        # Count projects that depend on this project
        stmt = select(LinkModel).where(
            and_(
                LinkModel.type_id == 'lt_project_depends_on',
                LinkModel.target_id == project_id
            )
        )
        dependent_count = len(session.scalars(stmt).all())
        
        # Boost of 20 points per dependent, max 100
        return min(100.0, dependent_count * 20.0)
    
    def _calculate_risk_penalty(self, project_data: Dict[str, Any]) -> float:
        """
        Calculate risk penalty based on risk score.
        
        Higher risk scores reduce priority to account for uncertainty.
        """
        risk_score = project_data.get('risk_score', 0)
        return risk_score * self.RISK_PENALTY_FACTOR
