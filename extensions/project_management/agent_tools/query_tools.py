"""
Query Tools for AI Agents

Tools for querying project management data.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy import select, and_, or_, func

from ..schedulers.base import SchedulerBase, ObjectModel

logger = logging.getLogger(__name__)


async def query_projects(
    db_adapter,
    filter: Optional[Dict[str, Any]] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search and filter projects.
    
    Args:
        db_adapter: Database adapter
        filter: Filter criteria
            - status: Project status ('active', 'planning', 'completed', etc.)
            - customer_id: Filter by customer
            - priority_min: Minimum priority score
            - pm_id: Filter by project manager
            - due_before: ISO date string
            - due_after: ISO date string
        limit: Maximum results
        
    Returns:
        Search results
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_project',
                ObjectModel.status != 'deleted'
            )
        ).limit(limit)
        
        # Apply filters
        filter = filter or {}
        
        if 'status' in filter:
            stmt = stmt.where(
                ObjectModel.data['status'].astext == filter['status']
            )
        
        if 'customer_id' in filter:
            stmt = stmt.where(
                ObjectModel.data['customer_id'].astext == filter['customer_id']
            )
        
        if 'pm_id' in filter:
            stmt = stmt.where(
                ObjectModel.data['pm_id'].astext == filter['pm_id']
            )
        
        if 'priority_min' in filter:
            stmt = stmt.where(
                ObjectModel.data['priority_score'].as_float() >= filter['priority_min']
            )
        
        projects = session.scalars(stmt).all()
        
        results = []
        for project in projects:
            results.append({
                'id': project.id,
                'name': project.data.get('name'),
                'status': project.data.get('status'),
                'priority_score': project.data.get('priority_score'),
                'risk_score': project.data.get('risk_score'),
                'planned_start': project.data.get('planned_start'),
                'planned_end': project.data.get('planned_end'),
                'customer_id': project.data.get('customer_id'),
                'pm_id': project.data.get('pm_id'),
                'health_status': project.data.get('health_status')
            })
        
        return {
            'count': len(results),
            'projects': results
        }


async def query_tasks(
    db_adapter,
    filter: Optional[Dict[str, Any]] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search and filter tasks.
    
    Args:
        db_adapter: Database adapter
        filter: Filter criteria
            - status: Task status
            - project_id: Filter by project
            - assignee_id: Filter by assignee
            - priority: Task priority ('critical', 'high', 'medium', 'low')
            - sprint_id: Filter by sprint
            - due_before: ISO date string
            - due_after: ISO date string
            - predicted_delay_min: Minimum delay probability
        limit: Maximum results
        
    Returns:
        Search results
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_task',
                ObjectModel.status != 'deleted'
            )
        ).limit(limit)
        
        filter = filter or {}
        
        if 'status' in filter:
            stmt = stmt.where(
                ObjectModel.data['status'].astext == filter['status']
            )
        
        if 'project_id' in filter:
            stmt = stmt.where(
                ObjectModel.data['project_id'].astext == filter['project_id']
            )
        
        if 'priority' in filter:
            stmt = stmt.where(
                ObjectModel.data['priority'].astext == filter['priority']
            )
        
        if 'predicted_delay_min' in filter:
            stmt = stmt.where(
                ObjectModel.data['predicted_delay_probability'].as_float() >= filter['predicted_delay_min']
            )
        
        tasks = session.scalars(stmt).all()
        
        # Post-filter by assignee if specified
        if 'assignee_id' in filter:
            # Get tasks assigned to this person
            assignee_id = filter['assignee_id']
            stmt_assignments = select(ObjectModel).where(
                and_(
                    ObjectModel.type_id == 'ot_assignment',
                    ObjectModel.data['person_id'].astext == assignee_id
                )
            )
            assignments = session.scalars(stmt_assignments).all()
            assigned_task_ids = {a.data.get('task_id') for a in assignments}
            
            tasks = [t for t in tasks if t.id in assigned_task_ids]
        
        results = []
        for task in tasks:
            results.append({
                'id': task.id,
                'title': task.data.get('title'),
                'status': task.data.get('status'),
                'priority': task.data.get('priority'),
                'project_id': task.data.get('project_id'),
                'estimated_hours': task.data.get('estimated_hours'),
                'due_date': task.data.get('due_date'),
                'predicted_delay_probability': task.data.get('predicted_delay_probability'),
                'predicted_completion_date': task.data.get('predicted_completion_date')
            })
        
        return {
            'count': len(results),
            'tasks': results
        }


async def get_project_health(
    db_adapter,
    project_id: str
) -> Dict[str, Any]:
    """
    Get comprehensive health metrics for a project.
    
    Args:
        db_adapter: Database adapter
        project_id: Project to analyze
        
    Returns:
        Health metrics
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        project = base.get_object_by_id(session, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get project tasks
        task_links = base.get_linked_objects(
            session, project_id, link_type_id='lt_project_has_task'
        )
        
        total_tasks = len(task_links)
        completed_tasks = 0
        at_risk_tasks = 0
        blocked_tasks = 0
        
        total_estimated_hours = 0
        total_actual_hours = 0
        
        for link in task_links:
            task = link['object']
            status = task.data.get('status')
            
            if status == 'done':
                completed_tasks += 1
            elif status == 'blocked':
                blocked_tasks += 1
            
            delay_prob = task.data.get('predicted_delay_probability', 0)
            if delay_prob > 0.7:
                at_risk_tasks += 1
            
            total_estimated_hours += task.data.get('estimated_hours', 0)
            total_actual_hours += task.data.get('actual_hours', 0)
        
        # Calculate metrics
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Health score calculation
        health_score = 100
        health_score -= at_risk_tasks * 5
        health_score -= blocked_tasks * 10
        health_score -= max(0, (project.data.get('risk_score', 0) - 50))
        health_score = max(0, min(100, health_score))
        
        # Determine status
        if health_score >= 80:
            status = 'healthy'
        elif health_score >= 60:
            status = 'at_risk'
        else:
            status = 'critical'
        
        # Calculate timeline status
        planned_end = project.data.get('planned_end')
        timeline_status = 'on_track'
        
        if planned_end:
            if isinstance(planned_end, str):
                planned_end = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
            
            if datetime.utcnow() > planned_end and completion_rate < 90:
                timeline_status = 'overdue'
            elif completion_rate < 50 and (planned_end - datetime.utcnow()).days < 14:
                timeline_status = 'at_risk'
        
        return {
            'project_id': project_id,
            'project_name': project.data.get('name'),
            'health_score': round(health_score, 2),
            'status': status,
            'timeline_status': timeline_status,
            'metrics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round(completion_rate, 2),
                'at_risk_tasks': at_risk_tasks,
                'blocked_tasks': blocked_tasks,
                'total_estimated_hours': total_estimated_hours,
                'total_actual_hours': total_actual_hours
            },
            'risk_factors': {
                'risk_score': project.data.get('risk_score'),
                'predicted_delay_probability': project.data.get('predicted_delay_probability'),
                'priority_score': project.data.get('priority_score')
            },
            'recommendations': _generate_health_recommendations(
                health_score, at_risk_tasks, blocked_tasks, timeline_status
            )
        }


async def get_person_utilization(
    db_adapter,
    person_id: str,
    date_range: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get resource utilization for a person.
    
    Args:
        db_adapter: Database adapter
        person_id: Person to analyze
        date_range: Optional date range {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
        
    Returns:
        Utilization metrics
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        person = base.get_object_by_id(session, person_id)
        if not person:
            raise ValueError(f"Person {person_id} not found")
        
        # Get assignments
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['person_id'].astext == person_id,
                ObjectModel.status == 'active'
            )
        )
        assignments = session.scalars(stmt).all()
        
        # Calculate utilization by day
        from collections import defaultdict
        daily_allocation = defaultdict(float)
        
        for assignment in assignments:
            start = assignment.data.get('planned_start')
            end = assignment.data.get('planned_end')
            allocation = assignment.data.get('allocation_percent', 100)
            
            if not start or not end:
                continue
            
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace('Z', '+00:00'))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Filter by date range if specified
            if date_range:
                range_start = datetime.fromisoformat(date_range['start'])
                range_end = datetime.fromisoformat(date_range['end'])
                
                if end < range_start or start > range_end:
                    continue
            
            current = start
            while current <= end:
                date_str = current.strftime('%Y-%m-%d')
                daily_allocation[date_str] += allocation
                current += __import__('datetime').timedelta(days=1)
        
        # Calculate statistics
        if daily_allocation:
            allocations = list(daily_allocation.values())
            avg_utilization = sum(allocations) / len(allocations)
            max_utilization = max(allocations)
            min_utilization = min(allocations)
            overallocated_days = sum(1 for a in allocations if a > 100)
        else:
            avg_utilization = 0
            max_utilization = 0
            min_utilization = 0
            overallocated_days = 0
        
        # Get current assignments summary
        current_assignments = []
        for assignment in assignments:
            task_id = assignment.data.get('task_id')
            task = base.get_object_by_id(session, task_id)
            
            current_assignments.append({
                'assignment_id': assignment.id,
                'task_id': task_id,
                'task_title': task.data.get('title') if task else 'Unknown',
                'allocation_percent': assignment.data.get('allocation_percent'),
                'planned_start': assignment.data.get('planned_start'),
                'planned_end': assignment.data.get('planned_end'),
                'planned_hours': assignment.data.get('planned_hours')
            })
        
        return {
            'person_id': person_id,
            'person_name': person.data.get('name'),
            'date_range': date_range,
            'utilization': {
                'average': round(avg_utilization, 2),
                'maximum': round(max_utilization, 2),
                'minimum': round(min_utilization, 2),
                'overallocated_days': overallocated_days
            },
            'status': 'overallocated' if max_utilization > 100 else 'available' if avg_utilization < 70 else 'optimal',
            'current_assignments': current_assignments,
            'daily_breakdown': dict(daily_allocation)
        }


def _generate_health_recommendations(
    health_score: float,
    at_risk_tasks: int,
    blocked_tasks: int,
    timeline_status: str
) -> List[str]:
    """Generate health recommendations."""
    recommendations = []
    
    if health_score < 60:
        recommendations.append("Project is in critical state. Immediate intervention required.")
    elif health_score < 80:
        recommendations.append("Project health is at risk. Review and address issues promptly.")
    
    if at_risk_tasks > 0:
        recommendations.append(f"Address {at_risk_tasks} at-risk tasks before they impact timeline.")
    
    if blocked_tasks > 0:
        recommendations.append(f"Resolve {blocked_tasks} blocked tasks to unblock progress.")
    
    if timeline_status == 'overdue':
        recommendations.append("Project is overdue. Consider scope reduction or deadline extension.")
    elif timeline_status == 'at_risk':
        recommendations.append("Timeline is at risk. Accelerate progress or adjust expectations.")
    
    if not recommendations:
        recommendations.append("Project is on track. Continue current approach.")
    
    return recommendations
