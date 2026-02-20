"""
Action Tools for AI Agents

Tools that can modify data (with appropriate safeguards).
"""

import logging
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from sqlalchemy import select, and_

from ..schedulers.base import SchedulerBase, ObjectModel

logger = logging.getLogger(__name__)


async def create_nudge(
    db_adapter,
    type: str,
    title: str,
    description: str,
    recipient_ids: List[str],
    related_project_id: Optional[str] = None,
    related_task_id: Optional[str] = None,
    severity: str = "info"
) -> Dict[str, Any]:
    """
    Create a manual nudge/notification.
    
    Args:
        db_adapter: Database adapter
        type: Nudge type ('risk', 'opportunity', 'conflict', 'suggestion')
        title: Short title
        description: Detailed description
        recipient_ids: List of person IDs to notify
        related_project_id: Optional related project
        related_task_id: Optional related task
        severity: Severity level ('info', 'warning', 'critical')
        
    Returns:
        Created nudge info
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        created_nudges = []
        
        for recipient_id in recipient_ids:
            # Verify recipient exists
            recipient = base.get_object_by_id(session, recipient_id)
            if not recipient:
                logger.warning(f"Recipient {recipient_id} not found, skipping")
                continue
            
            nudge_data = {
                'type': type,
                'severity': severity,
                'title': title,
                'description': description,
                'recipient_id': recipient_id,
                'related_project_id': related_project_id,
                'related_task_id': related_task_id,
                'related_person_id': None,
                'context_data': {
                    'created_by_agent': True,
                    'created_at': datetime.utcnow().isoformat()
                },
                'ai_confidence': 1.0,  # Manual nudges have high confidence
                'status': 'new',
                'created_at': datetime.utcnow().isoformat()
            }
            
            nudge = ObjectModel(
                id=str(uuid.uuid4()),
                type_id='ot_nudge',
                data=nudge_data,
                status='active'
            )
            
            session.add(nudge)
            created_nudges.append({
                'nudge_id': nudge.id,
                'recipient_id': recipient_id,
                'recipient_name': recipient.data.get('name')
            })
        
        session.commit()
        
        logger.info(f"Created {len(created_nudges)} nudges")
        
        return {
            'success': True,
            'nudges_created': len(created_nudges),
            'nudges': created_nudges,
            'title': title,
            'type': type,
            'severity': severity
        }


async def reassign_task(
    db_adapter,
    task_id: str,
    to_person_id: str,
    from_person_id: Optional[str] = None,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reassign a task from one person to another.
    
    Args:
        db_adapter: Database adapter
        task_id: Task to reassign
        to_person_id: New assignee
        from_person_id: Current assignee (optional, for verification)
        reason: Reason for reassignment
        
    Returns:
        Reassignment result
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        # Verify task exists
        task = base.get_object_by_id(session, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Verify new assignee exists
        to_person = base.get_object_by_id(session, to_person_id)
        if not to_person:
            raise ValueError(f"Person {to_person_id} not found")
        
        # Find existing assignment
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['task_id'].astext == task_id,
                ObjectModel.status == 'active'
            )
        )
        existing_assignment = session.scalar(stmt)
        
        changes = {
            'task_id': task_id,
            'task_title': task.data.get('title'),
            'to_person_id': to_person_id,
            'to_person_name': to_person.data.get('name')
        }
        
        if existing_assignment:
            current_person_id = existing_assignment.data.get('person_id')
            
            # Verify if from_person_id matches
            if from_person_id and current_person_id != from_person_id:
                raise ValueError(
                    f"Task is assigned to {current_person_id}, not {from_person_id}"
                )
            
            # Get current assignee info
            if current_person_id:
                from_person = base.get_object_by_id(session, current_person_id)
                changes['from_person_id'] = current_person_id
                changes['from_person_name'] = from_person.data.get('name') if from_person else 'Unknown'
            
            # Cancel existing assignment
            existing_assignment.data['status'] = 'cancelled'
            existing_assignment.data['cancelled_at'] = datetime.utcnow().isoformat()
            existing_assignment.data['cancellation_reason'] = reason or 'Reassigned'
            existing_assignment.status = 'inactive'
        
        # Create new assignment
        new_assignment_data = {
            'person_id': to_person_id,
            'task_id': task_id,
            'allocation_percent': existing_assignment.data.get('allocation_percent', 100) if existing_assignment else 100,
            'role_in_task': existing_assignment.data.get('role_in_task', 'primary') if existing_assignment else 'primary',
            'planned_start': existing_assignment.data.get('planned_start') if existing_assignment else datetime.utcnow().isoformat(),
            'planned_end': existing_assignment.data.get('planned_end') if existing_assignment else None,
            'planned_hours': existing_assignment.data.get('planned_hours', task.data.get('estimated_hours', 0)) if existing_assignment else task.data.get('estimated_hours', 0),
            'status': 'planned'
        }
        
        new_assignment = ObjectModel(
            id=str(uuid.uuid4()),
            type_id='ot_assignment',
            data=new_assignment_data,
            status='active'
        )
        
        session.add(new_assignment)
        
        # Update task if needed
        task.data['predicted_delay_probability'] = None  # Recalculate needed
        task.version += 1
        
        session.commit()
        
        # Create notification for new assignee
        await create_nudge(
            db_adapter,
            type='suggestion',
            title=f"Task assigned: {task.data.get('title', 'New Task')}",
            description=f"You have been assigned to task '{task.data.get('title')}'. "
                       f"{reason if reason else ''}",
            recipient_ids=[to_person_id],
            related_task_id=task_id,
            related_project_id=task.data.get('project_id'),
            severity='info'
        )
        
        logger.info(f"Reassigned task {task_id} to {to_person_id}")
        
        return {
            'success': True,
            'task_id': task_id,
            'assignment_id': new_assignment.id,
            'changes': changes,
            'reason': reason
        }


async def create_task(
    db_adapter,
    project_id: str,
    title: str,
    description: Optional[str] = None,
    estimated_hours: Optional[float] = None,
    priority: str = "medium",
    assignee_id: Optional[str] = None,
    due_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new task in a project.
    
    Args:
        db_adapter: Database adapter
        project_id: Parent project
        title: Task title
        description: Task description
        estimated_hours: Estimated effort
        priority: Task priority ('critical', 'high', 'medium', 'low')
        assignee_id: Optional person to assign
        due_date: Optional due date (ISO format)
        
    Returns:
        Created task info
    """
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        # Verify project exists
        project = base.get_object_by_id(session, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        task_data = {
            'title': title,
            'description': description,
            'project_id': project_id,
            'type': 'feature',
            'priority': priority,
            'status': 'backlog',
            'estimated_hours': estimated_hours or 8,
            'due_date': due_date,
            'created_at': datetime.utcnow().isoformat()
        }
        
        task = ObjectModel(
            id=str(uuid.uuid4()),
            type_id='ot_task',
            data=task_data,
            status='active'
        )
        
        session.add(task)
        
        # Create assignment if specified
        assignment_id = None
        if assignee_id:
            assignee = base.get_object_by_id(session, assignee_id)
            if assignee:
                assignment_data = {
                    'person_id': assignee_id,
                    'task_id': task.id,
                    'allocation_percent': 100,
                    'role_in_task': 'primary',
                    'planned_start': datetime.utcnow().isoformat(),
                    'planned_end': due_date,
                    'planned_hours': estimated_hours or 8,
                    'status': 'planned'
                }
                
                assignment = ObjectModel(
                    id=str(uuid.uuid4()),
                    type_id='ot_assignment',
                    data=assignment_data,
                    status='active'
                )
                
                session.add(assignment)
                assignment_id = assignment.id
        
        session.commit()
        
        # Notify project manager
        pm_id = project.data.get('pm_id')
        if pm_id:
            await create_nudge(
                db_adapter,
                type='suggestion',
                title=f"New task created: {title}",
                description=f"A new task has been created in project '{project.data.get('name')}'.",
                recipient_ids=[pm_id],
                related_task_id=task.id,
                related_project_id=project_id,
                severity='info'
            )
        
        return {
            'success': True,
            'task_id': task.id,
            'title': title,
            'project_id': project_id,
            'assignment_id': assignment_id,
            'assigned_to': assignee_id
        }


async def update_task_status(
    db_adapter,
    task_id: str,
    new_status: str,
    actual_hours: Optional[float] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update task status.
    
    Args:
        db_adapter: Database adapter
        task_id: Task to update
        new_status: New status ('backlog', 'todo', 'in_progress', 'review', 'done')
        actual_hours: Hours spent (for done status)
        notes: Status update notes
        
    Returns:
        Update result
    """
    base = SchedulerBase(db_adapter)
    
    valid_statuses = ['backlog', 'todo', 'in_progress', 'review', 'done', 'cancelled']
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
    
    with base.get_session() as session:
        task = base.get_object_by_id(session, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        old_status = task.data.get('status')
        
        # Update task
        task.data['status'] = new_status
        task.data['status_updated_at'] = datetime.utcnow().isoformat()
        task.data['status_notes'] = notes
        
        if new_status == 'done':
            task.data['actual_end'] = datetime.utcnow().isoformat()
            if actual_hours is not None:
                task.data['actual_hours'] = actual_hours
        elif new_status == 'in_progress' and old_status != 'in_progress':
            task.data['actual_start'] = datetime.utcnow().isoformat()
        
        task.version += 1
        
        # Update assignment if exists
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['task_id'].astext == task_id,
                ObjectModel.status == 'active'
            )
        )
        assignment = session.scalar(stmt)
        
        if assignment:
            if new_status == 'done':
                assignment.data['status'] = 'completed'
                assignment.data['actual_end'] = datetime.utcnow().isoformat()
                if actual_hours is not None:
                    assignment.data['actual_hours'] = actual_hours
            elif new_status == 'in_progress':
                assignment.data['status'] = 'active'
                assignment.data['actual_start'] = datetime.utcnow().isoformat()
        
        session.commit()
        
        logger.info(f"Updated task {task_id} status: {old_status} -> {new_status}")
        
        return {
            'success': True,
            'task_id': task_id,
            'old_status': old_status,
            'new_status': new_status,
            'updated_at': datetime.utcnow().isoformat()
        }
