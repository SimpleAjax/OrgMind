"""
Impact Analyzer Scheduler

Analyzes the ripple effects of changes across the project portfolio:
- Leave impact analysis (sick/vacation)
- Scope change impact (added/removed tasks)
- Resource conflict analysis
- Alternative resource suggestions

Usage:
    analyzer = ImpactAnalyzer(db_adapter, neo4j_adapter)
    
    # Analyze leave impact
    report = await analyzer.analyze_leave_impact(
        person_id="person_123",
        start_date="2026-03-01",
        end_date="2026-03-05"
    )
    
    # Analyze scope change
    report = await analyzer.analyze_scope_change_impact(
        project_id="proj_456",
        added_tasks=[{"title": "New Feature", "estimated_hours": 40}],
        removed_tasks=["task_789"]
    )
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, and_, or_

from .base import SchedulerBase, ObjectModel, LinkModel, Session

logger = logging.getLogger(__name__)


class ImpactLevel(str, Enum):
    """Impact severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ImpactReport:
    """Impact analysis report structure."""
    impact_type: str  # 'leave', 'scope_change', 'resource_conflict'
    impact_level: ImpactLevel
    summary: str
    
    # Affected entities
    affected_projects: List[Dict[str, Any]] = field(default_factory=list)
    affected_tasks: List[Dict[str, Any]] = field(default_factory=list)
    affected_people: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timeline impact
    timeline_changes: Dict[str, Any] = field(default_factory=dict)
    total_delay_days: int = 0
    
    # Resource impact
    resource_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Cost impact
    cost_impact: Dict[str, Any] = field(default_factory=dict)
    
    # Recommendations
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)
    alternative_resources: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    parameters: Dict[str, Any] = field(default_factory=dict)


class ImpactAnalyzer(SchedulerBase):
    """
    Analyzes the ripple effects of changes across the project portfolio.
    
    Uses Neo4j graph traversals for dependency analysis and PostgreSQL
    for resource allocation queries.
    """
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(self, analysis_type: str, **params) -> ImpactReport:
        """
        Run impact analysis based on type.
        
        Args:
            analysis_type: 'leave', 'scope_change', or 'resource_conflict'
            **params: Parameters specific to analysis type
            
        Returns:
            ImpactReport with analysis results
        """
        if analysis_type == 'leave':
            return await self.analyze_leave_impact(**params)
        elif analysis_type == 'scope_change':
            return await self.analyze_scope_change_impact(**params)
        elif analysis_type == 'resource_conflict':
            return await self.analyze_resource_conflict(**params)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    async def analyze_leave_impact(
        self,
        person_id: str,
        start_date: str,
        end_date: str,
        leave_type: str = "vacation"
    ) -> ImpactReport:
        """
        Analyze impact of a person going on leave.
        
        Args:
            person_id: Person going on leave
            start_date: Leave start date (ISO format)
            end_date: Leave end date (ISO format)
            leave_type: Type of leave (vacation, sick, training)
            
        Returns:
            ImpactReport with affected tasks and recommendations
        """
        self.logger.info(
            f"Analyzing leave impact for {person_id}: {start_date} to {end_date}"
        )
        
        with self.get_session() as session:
            person = self.get_object_by_id(session, person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")
            
            # Parse dates
            leave_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            leave_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            leave_days = (leave_end - leave_start).days + 1
            
            # Find affected assignments (tasks assigned during leave period)
            affected_assignments = self._get_assignments_during_period(
                session, person_id, leave_start, leave_end
            )
            
            # Get affected tasks with details
            affected_tasks = []
            affected_project_ids = set()
            total_delay_days = 0
            
            for assignment in affected_assignments:
                task = self.get_object_by_id(session, assignment.data.get('task_id'))
                if not task:
                    continue
                    
                project_id = task.data.get('project_id')
                if project_id:
                    affected_project_ids.add(project_id)
                
                # Calculate delay for this task
                task_delay = self._calculate_task_delay(
                    task, assignment, leave_days
                )
                total_delay_days += task_delay
                
                affected_tasks.append({
                    'task_id': task.id,
                    'task_title': task.data.get('title', 'Unknown'),
                    'project_id': project_id,
                    'assignment_id': assignment.id,
                    'planned_hours': assignment.data.get('planned_hours', 0),
                    'delay_days': task_delay,
                    'on_critical_path': self._is_on_critical_path(task.id)
                })
            
            # Get affected projects
            affected_projects = []
            for project_id in affected_project_ids:
                project = self.get_object_by_id(session, project_id)
                if project:
                    affected_projects.append({
                        'project_id': project_id,
                        'project_name': project.data.get('name', 'Unknown'),
                        'affected_tasks_count': sum(
                            1 for t in affected_tasks 
                            if t['project_id'] == project_id
                        )
                    })
            
            # Determine impact level
            impact_level = self._determine_impact_level(
                len(affected_tasks),
                total_delay_days,
                any(t['on_critical_path'] for t in affected_tasks)
            )
            
            # Find alternative resources
            alternatives = []
            for task_info in affected_tasks[:5]:  # Top 5 most critical
                task_alternatives = await self.find_alternative_resources(
                    task_info['task_id'],
                    exclude_person_id=person_id
                )
                if task_alternatives:
                    alternatives.append({
                        'task_id': task_info['task_id'],
                        'task_title': task_info['task_title'],
                        'suggested_replacements': task_alternatives[:3]
                    })
            
            # Build recommendations
            recommendations = self._build_leave_recommendations(
                affected_tasks, alternatives, leave_type
            )
            
            # Calculate cost impact
            cost_impact = self._calculate_leave_cost_impact(
                session, affected_tasks, leave_days
            )
            
            summary = (
                f"Leave impact: {len(affected_tasks)} tasks affected across "
                f"{len(affected_projects)} projects. "
                f"Estimated delay: {total_delay_days} days."
            )
            
            return ImpactReport(
                impact_type='leave',
                impact_level=impact_level,
                summary=summary,
                affected_projects=affected_projects,
                affected_tasks=affected_tasks,
                affected_people=[{
                    'person_id': person_id,
                    'person_name': person.data.get('name', 'Unknown'),
                    'leave_days': leave_days
                }],
                timeline_changes={'delay_days': total_delay_days},
                total_delay_days=total_delay_days,
                cost_impact=cost_impact,
                recommended_actions=recommendations,
                alternative_resources=alternatives,
                parameters={
                    'person_id': person_id,
                    'person_name': person.data.get('name'),
                    'start_date': start_date,
                    'end_date': end_date,
                    'leave_type': leave_type
                }
            )
    
    async def analyze_scope_change_impact(
        self,
        project_id: str,
        added_tasks: Optional[List[Dict[str, Any]]] = None,
        removed_tasks: Optional[List[str]] = None
    ) -> ImpactReport:
        """
        Analyze impact of adding/removing tasks from a project.
        
        Args:
            project_id: Project being modified
            added_tasks: List of task dicts to add (with estimated_hours, etc.)
            removed_tasks: List of task IDs to remove
            
        Returns:
            ImpactReport with scope change analysis
        """
        self.logger.info(f"Analyzing scope change impact for project {project_id}")
        
        added_tasks = added_tasks or []
        removed_tasks = removed_tasks or []
        
        with self.get_session() as session:
            project = self.get_object_by_id(session, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Calculate added work
            total_added_hours = sum(
                t.get('estimated_hours', 0) for t in added_tasks
            )
            
            # Calculate removed work
            total_removed_hours = 0
            removed_task_details = []
            for task_id in removed_tasks:
                task = self.get_object_by_id(session, task_id)
                if task:
                    hours = task.data.get('estimated_hours', 0)
                    total_removed_hours += hours
                    removed_task_details.append({
                        'task_id': task_id,
                        'title': task.data.get('title'),
                        'estimated_hours': hours
                    })
            
            # Net hours change
            net_hours = total_added_hours - total_removed_hours
            
            # Current project stats
            current_tasks = self.get_linked_objects(
                session, project_id, link_type_id='lt_project_has_task'
            )
            current_total_hours = sum(
                t['object'].data.get('estimated_hours', 0)
                for t in current_tasks
            )
            
            # Estimate new end date (simplified)
            current_end = project.data.get('planned_end')
            new_end_date = None
            if current_end and net_hours > 0:
                # Assuming 8 hours per day and 5 day work week
                additional_days = (net_hours / 8) * (7/5)  # Account for weekends
                if isinstance(current_end, str):
                    current_end = datetime.fromisoformat(current_end.replace('Z', '+00:00'))
                new_end_date = (current_end + timedelta(days=additional_days)).isoformat()
            
            # Check for resource conflicts
            resource_conflicts = []
            if added_tasks:
                resource_conflicts = self._check_resource_availability(
                    session, project_id, added_tasks
                )
            
            # Determine impact level
            impact_level = ImpactLevel.LOW
            if net_hours > 200 or len(resource_conflicts) > 3:
                impact_level = ImpactLevel.CRITICAL
            elif net_hours > 100 or len(resource_conflicts) > 1:
                impact_level = ImpactLevel.HIGH
            elif net_hours > 40:
                impact_level = ImpactLevel.MEDIUM
            
            # Build recommendations
            recommendations = []
            if net_hours > 0:
                recommendations.append({
                    'type': 'timeline',
                    'description': f'Consider extending project end date by {net_hours/40:.1f} weeks',
                    'priority': 'high' if net_hours > 80 else 'medium'
                })
            
            if resource_conflicts:
                recommendations.append({
                    'type': 'resource',
                    'description': f'{len(resource_conflicts)} resource conflicts detected. '
                                  f'Consider adding team members or adjusting timeline.',
                    'priority': 'high'
                })
            
            summary = (
                f"Scope change: +{len(added_tasks)} tasks ({total_added_hours}h), "
                f"-{len(removed_tasks)} tasks ({total_removed_hours}h). "
                f"Net change: {net_hours:+.0f} hours."
            )
            
            return ImpactReport(
                impact_type='scope_change',
                impact_level=impact_level,
                summary=summary,
                affected_projects=[{
                    'project_id': project_id,
                    'project_name': project.data.get('name', 'Unknown'),
                    'current_hours': current_total_hours,
                    'new_hours': current_total_hours + net_hours
                }],
                affected_tasks=[],  # Would be populated with actual analysis
                timeline_changes={
                    'current_end_date': project.data.get('planned_end'),
                    'new_end_date': new_end_date,
                    'delay_days': max(0, net_hours / 8 * (7/5)) if net_hours > 0 else 0
                },
                resource_conflicts=resource_conflicts,
                cost_impact={
                    'additional_hours': max(0, net_hours),
                    'cost_estimate': max(0, net_hours) * project.data.get('hourly_rate', 100)
                },
                recommended_actions=recommendations,
                parameters={
                    'project_id': project_id,
                    'added_tasks_count': len(added_tasks),
                    'removed_tasks_count': len(removed_tasks)
                }
            )
    
    async def analyze_resource_conflict(
        self,
        person_id: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> ImpactReport:
        """
        Analyze resource conflicts for a person.
        
        Args:
            person_id: Person to analyze
            date_range: Optional date range {'start': '...', 'end': '...'}
            
        Returns:
            ImpactReport with conflict analysis
        """
        with self.get_session() as session:
            person = self.get_object_by_id(session, person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")
            
            # Get all assignments for this person
            assignments = self._get_person_assignments(session, person_id)
            
            # Find conflicts (simplified - overlapping assignments)
            conflicts = []
            for i, assign1 in enumerate(assignments):
                for assign2 in assignments[i+1:]:
                    if self._assignments_overlap(assign1, assign2):
                        total_allocation = (
                            assign1.data.get('allocation_percent', 0) +
                            assign2.data.get('allocation_percent', 0)
                        )
                        if total_allocation > 100:
                            conflicts.append({
                                'assignment1': assign1.id,
                                'assignment2': assign2.id,
                                'date_range': self._get_overlap_period(assign1, assign2),
                                'total_allocation': total_allocation,
                                'excess': total_allocation - 100
                            })
            
            impact_level = ImpactLevel.LOW
            if len(conflicts) > 5:
                impact_level = ImpactLevel.CRITICAL
            elif len(conflicts) > 2:
                impact_level = ImpactLevel.HIGH
            elif len(conflicts) > 0:
                impact_level = ImpactLevel.MEDIUM
            
            summary = (
                f"Resource conflict analysis for {person.data.get('name')}: "
                f"{len(conflicts)} conflicts found."
            )
            
            return ImpactReport(
                impact_type='resource_conflict',
                impact_level=impact_level,
                summary=summary,
                affected_people=[{
                    'person_id': person_id,
                    'person_name': person.data.get('name', 'Unknown')
                }],
                resource_conflicts=conflicts,
                recommended_actions=[
                    {
                        'type': 'rebalance',
                        'description': f'Rebalance workload to resolve {len(conflicts)} conflicts',
                        'priority': 'high' if len(conflicts) > 2 else 'medium'
                    }
                ] if conflicts else [],
                parameters={'person_id': person_id}
            )
    
    async def find_alternative_resources(
        self,
        task_id: str,
        exclude_person_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find alternative resources for a task.
        
        Args:
            task_id: Task to find alternatives for
            exclude_person_id: Person to exclude (e.g., the one going on leave)
            limit: Maximum number of alternatives
            
        Returns:
            List of alternative people with match scores
        """
        with self.get_session() as session:
            task = self.get_object_by_id(session, task_id)
            if not task:
                return []
            
            # Get required skills for the task
            skill_requirements = self.get_linked_objects(
                session, task_id, link_type_id='lt_task_requires_skill'
            )
            
            # Get all active people
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            alternatives = []
            for person in people:
                if person.id == exclude_person_id:
                    continue
                
                # Check availability (simplified)
                has_capacity = self._check_person_capacity(session, person.id)
                if not has_capacity:
                    continue
                
                # Calculate skill match
                skill_match = self._calculate_skill_match(
                    session, person.id, skill_requirements
                )
                
                alternatives.append({
                    'person_id': person.id,
                    'person_name': person.data.get('name'),
                    'skill_match_score': skill_match['score'],
                    'matching_skills': skill_match['matches'],
                    'missing_skills': skill_match['missing']
                })
            
            # Sort by skill match score
            alternatives.sort(key=lambda x: x['skill_match_score'], reverse=True)
            
            return alternatives[:limit]
    
    # Helper methods
    
    def _get_assignments_during_period(
        self,
        session: Session,
        person_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[ObjectModel]:
        """Get assignments that overlap with a date period."""
        # Find assignments linked to this person
        stmt = select(LinkModel).where(
            and_(
                LinkModel.type_id == 'lt_assignment_to_person',
                LinkModel.target_id == person_id
            )
        )
        assignment_links = session.scalars(stmt).all()
        
        assignments = []
        for link in assignment_links:
            assignment = self.get_object_by_id(session, link.source_id)
            if assignment and assignment.status != 'deleted':
                # Check date overlap
                assign_start = assignment.data.get('planned_start')
                assign_end = assignment.data.get('planned_end')
                
                if assign_start and assign_end:
                    if isinstance(assign_start, str):
                        assign_start = datetime.fromisoformat(assign_start.replace('Z', '+00:00'))
                    if isinstance(assign_end, str):
                        assign_end = datetime.fromisoformat(assign_end.replace('Z', '+00:00'))
                    
                    # Check overlap
                    if assign_start <= end_date and assign_end >= start_date:
                        assignments.append(assignment)
        
        return assignments
    
    def _calculate_task_delay(
        self,
        task: ObjectModel,
        assignment: ObjectModel,
        leave_days: int
    ) -> int:
        """Calculate delay in days for a task due to leave."""
        # Simple calculation: if assignment is fully during leave, delay by leave days
        # In production, this would consider:
        # - Partial overlaps
        # - Task dependencies
        # - Critical path analysis
        planned_hours = assignment.data.get('planned_hours', 0)
        daily_hours = 8  # Assume 8 hours per day
        
        assignment_days = planned_hours / daily_hours
        return min(int(assignment_days), leave_days)
    
    def _is_on_critical_path(self, task_id: str) -> bool:
        """Check if task is on the critical path using Neo4j."""
        if not self.neo4j:
            return False
            
        try:
            # Query for tasks that depend on this task
            query = """
            MATCH (t:Object {id: $task_id})-[:lt_task_blocks]->(dependent:Object)
            RETURN count(dependent) as dependent_count
            """
            result = self.neo4j.execute_read(query, {'task_id': task_id})
            
            # If many tasks depend on this, it's likely on critical path
            if result and result[0].get('dependent_count', 0) > 2:
                return True
                
        except Exception as e:
            self.logger.warning(f"Neo4j query failed for critical path: {e}")
            
        return False
    
    def _determine_impact_level(
        self,
        affected_tasks_count: int,
        total_delay_days: int,
        has_critical_path: bool
    ) -> ImpactLevel:
        """Determine overall impact level."""
        if affected_tasks_count > 10 or total_delay_days > 20 or has_critical_path:
            return ImpactLevel.CRITICAL
        elif affected_tasks_count > 5 or total_delay_days > 10:
            return ImpactLevel.HIGH
        elif affected_tasks_count > 2 or total_delay_days > 5:
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW
    
    def _build_leave_recommendations(
        self,
        affected_tasks: List[Dict],
        alternatives: List[Dict],
        leave_type: str
    ) -> List[Dict[str, Any]]:
        """Build recommendations for leave impact."""
        recommendations = []
        
        if affected_tasks:
            recommendations.append({
                'type': 'reassignment',
                'description': f'Reassign {len(affected_tasks)} tasks to other team members',
                'priority': 'high',
                'action_data': {'affected_count': len(affected_tasks)}
            })
        
        if alternatives:
            recommendations.append({
                'type': 'alternatives',
                'description': f'Found {len(alternatives)} tasks with available alternatives',
                'priority': 'medium',
                'action_data': {'alternatives': alternatives}
            })
        
        if leave_type == 'sick':
            recommendations.append({
                'type': 'urgent',
                'description': 'Sick leave requires immediate attention - reassign critical tasks ASAP',
                'priority': 'critical'
            })
        
        return recommendations
    
    def _calculate_leave_cost_impact(
        self,
        session: Session,
        affected_tasks: List[Dict],
        leave_days: int
    ) -> Dict[str, Any]:
        """Calculate cost impact of leave."""
        # This is a simplified calculation
        total_hours = sum(t.get('planned_hours', 0) for t in affected_tasks)
        
        # Assume average cost per hour
        avg_hourly_rate = 75  # Would be fetched from config or person data
        
        return {
            'affected_hours': total_hours,
            'estimated_cost_impact': total_hours * avg_hourly_rate * 0.1,  # 10% cost increase
            'notes': 'Cost impact includes potential delays and reassignment overhead'
        }
    
    def _check_resource_availability(
        self,
        session: Session,
        project_id: str,
        added_tasks: List[Dict]
    ) -> List[Dict]:
        """Check if resources are available for added tasks."""
        # Simplified - in production would check actual capacity
        conflicts = []
        
        # Get current team allocations
        project_tasks = self.get_linked_objects(
            session, project_id, link_type_id='lt_project_has_task'
        )
        
        total_allocated_hours = sum(
            t['object'].data.get('estimated_hours', 0)
            for t in project_tasks
        )
        
        new_task_hours = sum(t.get('estimated_hours', 0) for t in added_tasks)
        
        # Arbitrary threshold: if total > 1000 hours, flag potential conflict
        if total_allocated_hours + new_task_hours > 1000:
            conflicts.append({
                'type': 'capacity',
                'description': f'Project approaching capacity limit',
                'current_hours': total_allocated_hours,
                'additional_hours': new_task_hours
            })
        
        return conflicts
    
    def _get_person_assignments(
        self,
        session: Session,
        person_id: str
    ) -> List[ObjectModel]:
        """Get all assignments for a person."""
        stmt = select(LinkModel).where(
            and_(
                LinkModel.type_id == 'lt_assignment_to_person',
                LinkModel.target_id == person_id
            )
        )
        links = session.scalars(stmt).all()
        
        assignments = []
        for link in links:
            assignment = self.get_object_by_id(session, link.source_id)
            if assignment and assignment.status != 'deleted':
                assignments.append(assignment)
        
        return assignments
    
    def _assignments_overlap(
        self,
        assign1: ObjectModel,
        assign2: ObjectModel
    ) -> bool:
        """Check if two assignments overlap in time."""
        start1 = assign1.data.get('planned_start')
        end1 = assign1.data.get('planned_end')
        start2 = assign2.data.get('planned_start')
        end2 = assign2.data.get('planned_end')
        
        if not all([start1, end1, start2, end2]):
            return False
        
        # Parse dates if strings
        for date_val in [start1, end1, start2, end2]:
            if isinstance(date_val, str):
                date_val = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
        
        return start1 <= end2 and start2 <= end1
    
    def _get_overlap_period(
        self,
        assign1: ObjectModel,
        assign2: ObjectModel
    ) -> Dict[str, str]:
        """Get the overlap period between two assignments."""
        start1 = assign1.data.get('planned_start')
        end1 = assign1.data.get('planned_end')
        start2 = assign2.data.get('planned_start')
        end2 = assign2.data.get('planned_end')
        
        return {
            'start': max(str(start1), str(start2)),
            'end': min(str(end1), str(end2))
        }
    
    def _check_person_capacity(
        self,
        session: Session,
        person_id: str
    ) -> bool:
        """Check if person has capacity for new work."""
        # Simplified - would check actual allocation %
        assignments = self._get_person_assignments(session, person_id)
        
        total_allocation = sum(
            a.data.get('allocation_percent', 0)
            for a in assignments
        )
        
        return total_allocation < 80  # Has capacity if < 80% allocated
    
    def _calculate_skill_match(
        self,
        session: Session,
        person_id: str,
        skill_requirements: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate how well a person matches skill requirements."""
        if not skill_requirements:
            return {'score': 100, 'matches': [], 'missing': []}
        
        # Get person's skills
        person_skills = self.get_linked_objects(
            session, person_id, link_type_id='lt_person_has_skill'
        )
        
        person_skill_map = {
            s['object'].data.get('skill_id'): s['link_data'].get('proficiency_level', 1)
            for s in person_skills
        }
        
        matches = []
        missing = []
        total_score = 0
        
        for req in skill_requirements:
            req_skill_id = req['object'].data.get('skill_id')
            req_level = req['object'].data.get('minimum_proficiency', 1)
            
            person_level = person_skill_map.get(req_skill_id, 0)
            
            if person_level >= req_level:
                matches.append({
                    'skill_id': req_skill_id,
                    'required': req_level,
                    'actual': person_level
                })
                total_score += 100
            else:
                missing.append({
                    'skill_id': req_skill_id,
                    'required': req_level,
                    'actual': person_level
                })
                if person_level > 0:
                    total_score += (person_level / req_level) * 50
        
        avg_score = total_score / len(skill_requirements) if skill_requirements else 100
        
        return {
            'score': round(avg_score, 2),
            'matches': matches,
            'missing': missing
        }
