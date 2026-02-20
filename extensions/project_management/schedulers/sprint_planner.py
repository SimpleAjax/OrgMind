"""
Sprint Planner Scheduler

AI-assisted sprint planning that recommends optimal task selection for sprints.

Optimization Goals:
1. Maximize value delivery (priority × business value)
2. Balance load across team members
3. Respect capacity constraints
4. Minimize risk

Algorithm: Modified knapsack with multiple constraints

Usage:
    planner = SprintPlanner(db_adapter, neo4j_adapter)
    
    # Generate sprint recommendations
    recommendation = await planner.generate_sprint_recommendation(sprint_id)
    
    # Check sprint health
    health = await planner.check_sprint_health(sprint_id)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid

from sqlalchemy import select, and_, or_

from .base import SchedulerBase, ObjectModel, Session

logger = logging.getLogger(__name__)


class SprintHealthStatus(str, Enum):
    """Sprint health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


@dataclass
class TaskScore:
    """Scoring result for a task in sprint context."""
    task_id: str
    task_title: str
    value_score: float  # 0-100
    effort_score: float  # 0-100 (higher = more effort)
    risk_score: float  # 0-100
    fit_score: float  # 0-100 (overall fit for sprint)
    recommended_assignee: Optional[str] = None
    recommended_assignee_name: Optional[str] = None
    skill_match_score: float = 0.0


@dataclass
class SprintRecommendation:
    """Sprint planning recommendation."""
    sprint_id: str
    sprint_name: str
    
    # Capacity
    total_capacity_hours: float
    recommended_commitment_hours: float
    utilization_target: float  # e.g., 0.85 for 85%
    
    # Recommended tasks
    recommended_tasks: List[TaskScore]
    total_value_score: float
    
    # Load balancing
    person_allocations: Dict[str, Dict[str, Any]]
    
    # Risk assessment
    overall_risk_score: float
    risk_factors: List[str]
    
    # Alternatives
    alternative_tasks: List[TaskScore]  # Tasks that didn't make the cut
    
    # Explanation
    recommendation_reasoning: str


@dataclass
class SprintHealth:
    """Sprint health check result."""
    sprint_id: str
    status: SprintHealthStatus
    health_score: float  # 0-100
    
    # Metrics
    completion_percentage: float
    scope_change_count: int
    blocked_tasks_count: int
    at_risk_tasks_count: int
    
    # Capacity
    committed_hours: float
    completed_hours: float
    remaining_capacity: float
    
    # Team
    team_utilization: Dict[str, float]
    overallocation_count: int
    
    # Predictions
    predicted_completion_rate: float
    predicted_end_date: Optional[str]
    
    # Issues
    issues: List[Dict[str, Any]]
    recommendations: List[str]


class SprintPlanner(SchedulerBase):
    """
    AI-assisted sprint planning scheduler.
    
    Uses a multi-constraint optimization algorithm to recommend
    the optimal set of tasks for a sprint.
    """
    
    # Sprint planning parameters
    TARGET_UTILIZATION = 0.85  # 85% capacity utilization target
    MAX_RISK_SCORE = 70  # Don't include tasks with risk above this
    MIN_TASK_VALUE = 20  # Minimum value score to include
    
    # Scoring weights
    VALUE_WEIGHT = 0.35
    EFFICIENCY_WEIGHT = 0.25
    RISK_WEIGHT = 0.20
    SKILL_MATCH_WEIGHT = 0.20
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(self, sprint_id: str) -> Dict[str, Any]:
        """
        Run sprint planning for a sprint.
        
        Args:
            sprint_id: Sprint to plan
            
        Returns:
            Summary of planning results
        """
        recommendation = await self.generate_sprint_recommendation(sprint_id)
        health = await self.check_sprint_health(sprint_id)
        
        return {
            'sprint_id': sprint_id,
            'sprint_name': recommendation.sprint_name,
            'recommended_tasks_count': len(recommendation.recommended_tasks),
            'total_capacity': recommendation.total_capacity_hours,
            'recommended_commitment': recommendation.recommended_commitment_hours,
            'utilization': recommendation.utilization_target,
            'risk_score': recommendation.overall_risk_score,
            'health_status': health.status.value,
            'health_score': health.health_score
        }
    
    async def generate_sprint_recommendation(
        self,
        sprint_id: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> SprintRecommendation:
        """
        Generate AI recommendation for sprint planning.
        
        Args:
            sprint_id: Sprint to plan
            constraints: Optional additional constraints
            
        Returns:
            SprintRecommendation with task recommendations
        """
        self.logger.info(f"Generating sprint recommendation for {sprint_id}")
        
        with self.get_session() as session:
            sprint = self.get_object_by_id(session, sprint_id)
            if not sprint:
                raise ValueError(f"Sprint {sprint_id} not found")
            
            # Get sprint participants and capacity
            participants = self._get_sprint_participants(session, sprint_id)
            total_capacity = sum(
                p.get('planned_capacity_hours', 80) for p in participants
            )
            
            # Calculate target commitment (85% of capacity)
            target_hours = total_capacity * self.TARGET_UTILIZATION
            
            # Get available tasks (from linked projects)
            available_tasks = self._get_available_tasks(session, sprint_id)
            
            # Score all tasks
            scored_tasks = []
            for task in available_tasks:
                score = await self.score_task_for_sprint(
                    session, task, sprint, participants
                )
                scored_tasks.append(score)
            
            # Sort by fit score (descending)
            scored_tasks.sort(key=lambda x: x.fit_score, reverse=True)
            
            # Optimize task selection using knapsack-like algorithm
            selected_tasks, alternative_tasks = self._optimize_task_selection(
                scored_tasks, target_hours, participants
            )
            
            # Calculate load distribution
            person_allocations = self._calculate_load_distribution(
                session, selected_tasks, participants
            )
            
            # Calculate overall risk
            risk_score, risk_factors = self._assess_sprint_risk(
                selected_tasks, person_allocations
            )
            
            # Generate reasoning
            reasoning = self._generate_recommendation_reasoning(
                selected_tasks, total_capacity, target_hours, risk_score
            )
            
            total_value = sum(t.value_score for t in selected_tasks)
            
            self.logger.info(
                f"Sprint recommendation for {sprint_id}: "
                f"{len(selected_tasks)} tasks, {total_value:.0f} total value"
            )
            
            return SprintRecommendation(
                sprint_id=sprint_id,
                sprint_name=sprint.data.get('name', 'Unknown Sprint'),
                total_capacity_hours=total_capacity,
                recommended_commitment_hours=sum(
                    t.effort_score for t in selected_tasks
                ),
                utilization_target=self.TARGET_UTILIZATION,
                recommended_tasks=selected_tasks,
                total_value_score=total_value,
                person_allocations=person_allocations,
                overall_risk_score=risk_score,
                risk_factors=risk_factors,
                alternative_tasks=alternative_tasks,
                recommendation_reasoning=reasoning
            )
    
    async def score_task_for_sprint(
        self,
        session: Session,
        task: ObjectModel,
        sprint: ObjectModel,
        participants: List[Dict[str, Any]]
    ) -> TaskScore:
        """
        Calculate how well a task fits in the sprint.
        
        Args:
            session: Database session
            task: Task to score
            sprint: Sprint context
            participants: Sprint participants
            
        Returns:
            TaskScore with all scoring components
        """
        task_data = task.data
        
        # 1. Value Score (35% weight)
        # Based on priority, business value, and strategic importance
        priority_score = task_data.get('priority_score', 50)
        business_value = task_data.get('business_value', 50)
        
        # Boost for deadline proximity
        due_date = task_data.get('due_date')
        deadline_boost = 0
        if due_date:
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            days_until = (due_date - self.now()).days
            if days_until <= 14:  # Due within sprint or next
                deadline_boost = 30
            elif days_until <= 30:
                deadline_boost = 15
        
        value_score = min(100, (priority_score + business_value) / 2 + deadline_boost)
        
        # 2. Effort Score (for capacity planning)
        estimated_hours = task_data.get('estimated_hours', 8)
        story_points = task_data.get('story_points', estimated_hours / 8)
        effort_score = estimated_hours
        
        # 3. Risk Score (lower is better)
        delay_probability = task_data.get('predicted_delay_probability', 0.3)
        risk_score = delay_probability * 100
        
        # Check dependencies
        dependency_risk = self._calculate_dependency_risk(session, task.id)
        risk_score = max(risk_score, dependency_risk)
        
        # 4. Skill Match Score
        best_assignee, best_match_score = self._find_best_assignee(
            session, task, participants
        )
        
        # Calculate overall fit score
        # Normalize effort (prefer tasks that fit well, not too big)
        ideal_task_size = 16  # hours
        effort_penalty = abs(estimated_hours - ideal_task_size) / ideal_task_size * 10
        
        fit_score = (
            self.VALUE_WEIGHT * value_score +
            self.EFFICIENCY_WEIGHT * (100 - effort_penalty) +
            self.RISK_WEIGHT * (100 - risk_score) +
            self.SKILL_MATCH_WEIGHT * best_match_score
        )
        
        return TaskScore(
            task_id=task.id,
            task_title=task_data.get('title', 'Unknown'),
            value_score=round(value_score, 2),
            effort_score=round(effort_score, 2),
            risk_score=round(risk_score, 2),
            fit_score=round(fit_score, 2),
            recommended_assignee=best_assignee,
            recommended_assignee_name=participants[0].get('name') if best_assignee and participants else None,
            skill_match_score=round(best_match_score, 2)
        )
    
    def _optimize_task_selection(
        self,
        scored_tasks: List[TaskScore],
        target_hours: float,
        participants: List[Dict[str, Any]]
    ) -> Tuple[List[TaskScore], List[TaskScore]]:
        """
        Select optimal set of tasks using a greedy algorithm.
        
        This is a multi-constraint knapsack problem. We use a greedy approach
        that prioritizes value density (value per hour) while respecting constraints.
        
        Args:
            scored_tasks: All scored tasks (sorted by fit_score)
            target_hours: Target capacity hours
            participants: Sprint participants for load balancing
            
        Returns:
            Tuple of (selected_tasks, alternative_tasks)
        """
        selected = []
        remaining_capacity = target_hours
        
        # Track person allocations
        person_hours = {p['id']: 0 for p in participants}
        person_capacity = {p['id']: p.get('planned_capacity_hours', 80) for p in participants}
        
        # Filter out high-risk tasks
        viable_tasks = [
            t for t in scored_tasks
            if t.risk_score <= self.MAX_RISK_SCORE and t.value_score >= self.MIN_TASK_VALUE
        ]
        
        for task in viable_tasks:
            # Check if task fits in remaining capacity
            if task.effort_score > remaining_capacity * 1.1:  # Allow 10% overflow
                continue
            
            # Check if we have someone to assign to
            if task.recommended_assignee:
                assignee_hours = person_hours.get(task.recommended_assignee, 0)
                assignee_capacity = person_capacity.get(task.recommended_assignee, 80)
                
                # Don't overload one person (max 60% of their capacity on one sprint)
                if assignee_hours + task.effort_score > assignee_capacity * 0.6:
                    # Try to find alternative assignee
                    alternative_found = False
                    for participant in participants:
                        if participant['id'] != task.recommended_assignee:
                            alt_hours = person_hours.get(participant['id'], 0)
                            alt_capacity = person_capacity.get(participant['id'], 80)
                            if alt_hours + task.effort_score <= alt_capacity * 0.6:
                                task.recommended_assignee = participant['id']
                                task.recommended_assignee_name = participant.get('name')
                                alternative_found = True
                                break
                    
                    if not alternative_found:
                        continue
            
            # Add task to selection
            selected.append(task)
            remaining_capacity -= task.effort_score
            
            # Update person allocation
            if task.recommended_assignee:
                person_hours[task.recommended_assignee] = person_hours.get(
                    task.recommended_assignee, 0
                ) + task.effort_score
            
            # Stop if we've reached target capacity
            if remaining_capacity <= 0:
                break
        
        # Tasks not selected are alternatives
        selected_ids = {t.task_id for t in selected}
        alternatives = [t for t in scored_tasks if t.task_id not in selected_ids]
        
        return selected, alternatives
    
    async def check_sprint_health(self, sprint_id: str) -> SprintHealth:
        """
        Check the health of a sprint.
        
        Args:
            sprint_id: Sprint to check
            
        Returns:
            SprintHealth with detailed metrics
        """
        self.logger.info(f"Checking sprint health for {sprint_id}")
        
        with self.get_session() as session:
            sprint = self.get_object_by_id(session, sprint_id)
            if not sprint:
                raise ValueError(f"Sprint {sprint_id} not found")
            
            # Get sprint tasks
            sprint_tasks = self._get_sprint_tasks(session, sprint_id)
            
            total_tasks = len(sprint_tasks)
            if total_tasks == 0:
                return SprintHealth(
                    sprint_id=sprint_id,
                    status=SprintHealthStatus.WARNING,
                    health_score=0,
                    completion_percentage=0,
                    scope_change_count=0,
                    blocked_tasks_count=0,
                    at_risk_tasks_count=0,
                    committed_hours=0,
                    completed_hours=0,
                    remaining_capacity=0,
                    team_utilization={},
                    overallocation_count=0,
                    predicted_completion_rate=0,
                    predicted_end_date=None,
                    issues=[{'type': 'empty_sprint', 'message': 'No tasks in sprint'}],
                    recommendations=['Add tasks to sprint']
                )
            
            # Calculate metrics
            completed_tasks = sum(
                1 for t in sprint_tasks
                if t.data.get('status') == 'done'
            )
            blocked_tasks = sum(
                1 for t in sprint_tasks
                if t.data.get('status') == 'blocked'
            )
            at_risk_tasks = sum(
                1 for t in sprint_tasks
                if t.data.get('predicted_delay_probability', 0) > 0.7
            )
            
            completion_pct = completed_tasks / total_tasks * 100
            
            # Calculate hours
            total_hours = sum(t.data.get('estimated_hours', 0) for t in sprint_tasks)
            completed_hours = sum(
                t.data.get('actual_hours', 0) for t in sprint_tasks
                if t.data.get('status') == 'done'
            )
            
            # Calculate team utilization
            participants = self._get_sprint_participants(session, sprint_id)
            team_utilization = self._calculate_team_utilization(
                session, sprint_id, participants
            )
            overallocation_count = sum(
                1 for u in team_utilization.values() if u > 100
            )
            
            # Predict completion
            sprint_start = sprint.data.get('start_date')
            sprint_end = sprint.data.get('end_date')
            
            predicted_rate = self._predict_completion_rate(
                sprint_tasks, sprint_start, sprint_end
            )
            
            # Identify issues
            issues = []
            recommendations = []
            
            if blocked_tasks > 0:
                issues.append({
                    'type': 'blocked_tasks',
                    'count': blocked_tasks,
                    'severity': 'high' if blocked_tasks > 2 else 'medium'
                })
                recommendations.append(f'Resolve {blocked_tasks} blocked tasks')
            
            if at_risk_tasks > 0:
                issues.append({
                    'type': 'at_risk_tasks',
                    'count': at_risk_tasks,
                    'severity': 'high'
                })
                recommendations.append(f'Address {at_risk_tasks} at-risk tasks')
            
            if overallocation_count > 0:
                issues.append({
                    'type': 'overallocation',
                    'count': overallocation_count,
                    'severity': 'high'
                })
                recommendations.append('Rebalance workload across team')
            
            if completion_pct < 20 and self._sprint_days_elapsed(sprint_start) > 5:
                issues.append({
                    'type': 'slow_progress',
                    'message': 'Sprint progress is behind schedule',
                    'severity': 'medium'
                })
                recommendations.append('Review sprint scope and priorities')
            
            # Calculate health score
            health_score = self._calculate_health_score(
                completion_pct, blocked_tasks, at_risk_tasks,
                overallocation_count, total_tasks
            )
            
            # Determine status
            if health_score >= 90:
                status = SprintHealthStatus.EXCELLENT
            elif health_score >= 75:
                status = SprintHealthStatus.GOOD
            elif health_score >= 60:
                status = SprintHealthStatus.WARNING
            elif health_score >= 40:
                status = SprintHealthStatus.AT_RISK
            else:
                status = SprintHealthStatus.CRITICAL
            
            # Predict end date
            predicted_end = None
            if sprint_end and predicted_rate < 100:
                remaining_work = 100 - completion_pct
                days_needed = remaining_work / (predicted_rate / 100)
                predicted_end = (self.now() + timedelta(days=days_needed)).isoformat()
            
            return SprintHealth(
                sprint_id=sprint_id,
                status=status,
                health_score=round(health_score, 2),
                completion_percentage=round(completion_pct, 2),
                scope_change_count=0,  # Would track from events
                blocked_tasks_count=blocked_tasks,
                at_risk_tasks_count=at_risk_tasks,
                committed_hours=total_hours,
                completed_hours=completed_hours,
                remaining_capacity=total_hours - completed_hours,
                team_utilization=team_utilization,
                overallocation_count=overallocation_count,
                predicted_completion_rate=round(predicted_rate, 2),
                predicted_end_date=predicted_end,
                issues=issues,
                recommendations=recommendations
            )
    
    def _get_sprint_participants(
        self,
        session: Session,
        sprint_id: str
    ) -> List[Dict[str, Any]]:
        """Get people participating in a sprint."""
        participant_links = self.get_linked_objects(
            session, sprint_id, link_type_id='lt_sprint_has_participant'
        )
        
        participants = []
        for link in participant_links:
            person = link['object']
            participants.append({
                'id': person.id,
                'name': person.data.get('name', 'Unknown'),
                'role': person.data.get('role', 'developer'),
                'planned_capacity_hours': link['link_data'].get('planned_capacity_hours', 80)
            })
        
        return participants
    
    def _get_available_tasks(
        self,
        session: Session,
        sprint_id: str
    ) -> List[ObjectModel]:
        """Get tasks available to add to sprint."""
        # Get tasks from projects linked to sprint
        sprint_projects = self.get_linked_objects(
            session, sprint_id, link_type_id='lt_project_in_sprint'
        )
        
        available = []
        for link in sprint_projects:
            project = link['object']
            project_tasks = self.get_linked_objects(
                session, project.id, link_type_id='lt_project_has_task'
            )
            
            for task_link in project_tasks:
                task = task_link['object']
                # Only include tasks not yet in sprint and not done
                if task.data.get('status') in ['backlog', 'todo']:
                    available.append(task)
        
        return available
    
    def _get_sprint_tasks(
        self,
        session: Session,
        sprint_id: str
    ) -> List[ObjectModel]:
        """Get tasks already in sprint."""
        # Get through SprintTask junction
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_sprint_task',
                ObjectModel.data['sprint_id'].astext == sprint_id,
                ObjectModel.status != 'deleted'
            )
        )
        sprint_task_links = session.scalars(stmt).all()
        
        tasks = []
        for link in sprint_task_links:
            task_id = link.data.get('task_id')
            task = self.get_object_by_id(session, task_id)
            if task:
                tasks.append(task)
        
        return tasks
    
    def _calculate_dependency_risk(
        self,
        session: Session,
        task_id: str
    ) -> float:
        """Calculate risk from task dependencies."""
        # Check if task is blocked by incomplete tasks
        blocking_links = self.get_linked_objects(
            session, task_id, link_type_id='lt_task_blocks'
        )
        
        risk = 0
        for link in blocking_links:
            # If it's a hard dependency and blocker is not done
            if link['link_data'].get('dependency_type') == 'hard':
                blocker = self.get_object_by_id(session, link['object'].id)
                if blocker and blocker.data.get('status') != 'done':
                    risk += 20  # 20 points per incomplete hard dependency
        
        return min(100, risk)
    
    def _find_best_assignee(
        self,
        session: Session,
        task: ObjectModel,
        participants: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], float]:
        """Find the best person to assign a task to."""
        # Get task skill requirements
        skill_reqs = self.get_linked_objects(
            session, task.id, link_type_id='lt_task_requires_skill'
        )
        
        if not skill_reqs:
            # No specific requirements - assign to least loaded person
            return participants[0]['id'] if participants else None, 70.0
        
        best_assignee = None
        best_score = 0
        
        for participant in participants:
            person_skills = self.get_linked_objects(
                session, participant['id'], link_type_id='lt_person_has_skill'
            )
            
            person_skill_map = {
                s['object'].data.get('skill_id'): s['link_data'].get('proficiency_level', 1)
                for s in person_skills
            }
            
            total_score = 0
            for req in skill_reqs:
                req_skill_id = req['object'].data.get('skill_id')
                req_level = req['object'].data.get('minimum_proficiency', 1)
                
                person_level = person_skill_map.get(req_skill_id, 0)
                if person_level >= req_level:
                    total_score += 100
                elif person_level > 0:
                    total_score += (person_level / req_level) * 50
            
            avg_score = total_score / len(skill_reqs) if skill_reqs else 100
            
            if avg_score > best_score:
                best_score = avg_score
                best_assignee = participant['id']
        
        return best_assignee, best_score
    
    def _calculate_load_distribution(
        self,
        session: Session,
        selected_tasks: List[TaskScore],
        participants: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate recommended load distribution."""
        allocations = {
            p['id']: {
                'name': p['name'],
                'allocated_hours': 0,
                'task_count': 0,
                'tasks': []
            }
            for p in participants
        }
        
        for task in selected_tasks:
            if task.recommended_assignee:
                alloc = allocations.get(task.recommended_assignee)
                if alloc:
                    alloc['allocated_hours'] += task.effort_score
                    alloc['task_count'] += 1
                    alloc['tasks'].append({
                        'task_id': task.task_id,
                        'title': task.task_title,
                        'hours': task.effort_score
                    })
        
        return allocations
    
    def _assess_sprint_risk(
        self,
        selected_tasks: List[TaskScore],
        person_allocations: Dict[str, Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        """Assess overall sprint risk."""
        if not selected_tasks:
            return 0, []
        
        # Average task risk
        avg_task_risk = sum(t.risk_score for t in selected_tasks) / len(selected_tasks)
        
        # Check for skill gaps (unassigned tasks)
        unassigned = sum(1 for t in selected_tasks if not t.recommended_assignee)
        
        # Check load imbalance
        loads = [a['allocated_hours'] for a in person_allocations.values()]
        load_variance = max(loads) - min(loads) if loads else 0
        imbalance_risk = min(30, load_variance / 5)
        
        risk_factors = []
        if avg_task_risk > 50:
            risk_factors.append(f"High average task risk ({avg_task_risk:.0f})")
        if unassigned > 0:
            risk_factors.append(f"{unassigned} tasks without clear assignee")
        if imbalance_risk > 15:
            risk_factors.append("Significant load imbalance across team")
        
        total_risk = min(100, avg_task_risk + imbalance_risk + unassigned * 10)
        
        return total_risk, risk_factors
    
    def _generate_recommendation_reasoning(
        self,
        selected_tasks: List[TaskScore],
        total_capacity: float,
        target_hours: float,
        risk_score: float
    ) -> str:
        """Generate human-readable explanation of recommendations."""
        total_value = sum(t.value_score for t in selected_tasks)
        total_hours = sum(t.effort_score for t in selected_tasks)
        
        reasoning = (
            f"Selected {len(selected_tasks)} tasks totaling {total_hours:.0f} hours "
            f"(target: {target_hours:.0f} hours, capacity: {total_capacity:.0f} hours). "
            f"Total value score: {total_value:.0f}. "
        )
        
        if risk_score > 50:
            reasoning += f"Sprint has elevated risk ({risk_score:.0f}/100). "
        
        if total_hours < target_hours * 0.9:
            reasoning += "Sprint is conservatively loaded. Consider adding more tasks if team capacity allows."
        elif total_hours > target_hours:
            reasoning += "Sprint is fully committed. Monitor progress closely."
        else:
            reasoning += "Sprint is optimally loaded."
        
        return reasoning
    
    def _calculate_team_utilization(
        self,
        session: Session,
        sprint_id: str,
        participants: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate utilization for each team member."""
        utilization = {}
        
        for participant in participants:
            person_id = participant['id']
            capacity = participant.get('planned_capacity_hours', 80)
            
            # Get assignments for this person during sprint
            assigned_hours = self._calculate_person_sprint_hours(
                session, person_id, sprint_id
            )
            
            utilization[person_id] = round((assigned_hours / capacity) * 100, 2) if capacity > 0 else 0
        
        return utilization
    
    def _calculate_person_sprint_hours(
        self,
        session: Session,
        person_id: str,
        sprint_id: str
    ) -> float:
        """Calculate assigned hours for a person in a sprint."""
        # Get assignments for this person
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['person_id'].astext == person_id,
                ObjectModel.status == 'active'
            )
        )
        assignments = session.scalars(stmt).all()
        
        total_hours = 0
        for assignment in assignments:
            # Check if assignment is for a task in this sprint
            task_id = assignment.data.get('task_id')
            if task_id:
                # Check if task is in sprint
                stmt = select(ObjectModel).where(
                    and_(
                        ObjectModel.type_id == 'ot_sprint_task',
                        ObjectModel.data['sprint_id'].astext == sprint_id,
                        ObjectModel.data['task_id'].astext == task_id
                    )
                )
                if session.scalars(stmt).first():
                    total_hours += assignment.data.get('planned_hours', 0)
        
        return total_hours
    
    def _predict_completion_rate(
        self,
        sprint_tasks: List[ObjectModel],
        sprint_start: Optional[str],
        sprint_end: Optional[str]
    ) -> float:
        """Predict completion rate based on current velocity."""
        if not sprint_tasks or not sprint_start or not sprint_end:
            return 100.0
        
        # Parse dates
        if isinstance(sprint_start, str):
            sprint_start = datetime.fromisoformat(sprint_start.replace('Z', '+00:00'))
        if isinstance(sprint_end, str):
            sprint_end = datetime.fromisoformat(sprint_end.replace('Z', '+00:00'))
        
        total_duration = (sprint_end - sprint_start).days
        elapsed = (self.now() - sprint_start).days
        
        if total_duration <= 0 or elapsed <= 0:
            return 100.0
        
        # Calculate completed work
        completed = sum(
            t.data.get('estimated_hours', 0)
            for t in sprint_tasks
            if t.data.get('status') == 'done'
        )
        total = sum(t.data.get('estimated_hours', 0) for t in sprint_tasks)
        
        if total == 0:
            return 100.0
        
        # If we're X% through time, we should be X% through work
        time_progress = elapsed / total_duration
        work_progress = completed / total
        
        # Predict if current pace continues
        if time_progress == 0:
            return 100.0
        
        predicted_completion = work_progress / time_progress * 100
        return min(100, predicted_completion)
    
    def _sprint_days_elapsed(self, sprint_start: Optional[str]) -> int:
        """Calculate days since sprint started."""
        if not sprint_start:
            return 0
        
        if isinstance(sprint_start, str):
            sprint_start = datetime.fromisoformat(sprint_start.replace('Z', '+00:00'))
        
        return max(0, (self.now() - sprint_start).days)
    
    def _calculate_health_score(
        self,
        completion_pct: float,
        blocked_count: int,
        at_risk_count: int,
        overallocation_count: int,
        total_tasks: int
    ) -> float:
        """Calculate overall health score."""
        # Base score from completion
        score = completion_pct
        
        # Penalties
        score -= blocked_count * 5  # -5 per blocked task
        score -= at_risk_count * 3  # -3 per at-risk task
        score -= overallocation_count * 10  # -10 per overallocated person
        
        return max(0, min(100, score))
