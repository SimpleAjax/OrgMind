"""
Projects API endpoints for Project Management.

Endpoints:
- GET /pm/projects/{id}/health - Project health
- POST /pm/projects/{id}/impact - Scope change impact
- GET /pm/projects/{id}/timeline - Project timeline
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter, get_neo4j_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase
from ..schedulers import ImpactAnalyzer
from ..agent_tools.query_tools import get_project_health
from ..agent_tools.analysis_tools import simulate_scope_change

logger = get_logger(__name__)
router = APIRouter()


class ScopeChangeRequest(BaseModel):
    """Request model for scope change simulation."""
    added_tasks: Optional[List[Dict[str, Any]]] = None
    removed_task_ids: Optional[List[str]] = None


class ScopeChangeResponse(BaseModel):
    """Response model for scope change."""
    impact_level: str
    summary: str
    current_state: Dict[str, Any]
    projected_state: Dict[str, Any]
    timeline_delay_days: float
    recommendations: List[str]
    can_commit: bool


@router.get("/{project_id}/health")
async def get_project_health_endpoint(
    project_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
) -> Dict[str, Any]:
    """
    Get comprehensive health metrics for a project.
    
    Returns:
        Health score, status, metrics, and recommendations
    """
    try:
        adapter = get_postgres_adapter()
        
        health = await get_project_health(adapter, project_id)
        
        return health
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get project health", project_id=project_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health: {str(e)}")


@router.post("/{project_id}/impact", response_model=ScopeChangeResponse)
async def analyze_scope_change_impact(
    project_id: Annotated[str, Path(...)],
    request: ScopeChangeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.write"))],
) -> ScopeChangeResponse:
    """
    Analyze the impact of a scope change.
    
    Simulate adding or removing tasks to see impact on timeline and resources.
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        result = await simulate_scope_change(
            adapter,
            neo4j,
            project_id,
            added_tasks=request.added_tasks,
            removed_task_ids=request.removed_task_ids
        )
        
        return ScopeChangeResponse(
            impact_level=result['impact_assessment']['impact_level'],
            summary=f"Net hours change: {result['simulation']['net_hours']:+.0f}",
            current_state=result['current_state'],
            projected_state=result['projected_state'],
            timeline_delay_days=result['impact_assessment'].get('timeline_delay_days', 0),
            recommendations=result['recommendations'],
            can_commit=result['can_commit']
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to analyze impact", project_id=project_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")


@router.get("/{project_id}/timeline")
async def get_project_timeline(
    project_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
) -> Dict[str, Any]:
    """
    Get project timeline with tasks and milestones.
    
    Returns:
        Timeline data with task dependencies and critical path
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            project = base.get_object_by_id(session, project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get project tasks
            task_links = base.get_linked_objects(
                session, project_id, link_type_id='lt_project_has_task'
            )
            
            timeline_items = []
            
            for link in task_links:
                task = link['object']
                task_data = task.data
                
                # Get assignees
                assignments = base.get_linked_objects(
                    session, task.id, link_type_id='lt_task_assigned_to'
                )
                assignees = []
                for assignment in assignments:
                    person_links = base.get_linked_objects(
                        session, assignment['object'].id,
                        link_type_id='lt_assignment_to_person'
                    )
                    for pl in person_links:
                        assignees.append({
                            'id': pl['object'].id,
                            'name': pl['object'].data.get('name')
                        })
                
                timeline_items.append({
                    'id': task.id,
                    'title': task_data.get('title'),
                    'status': task_data.get('status'),
                    'priority': task_data.get('priority'),
                    'estimated_hours': task_data.get('estimated_hours'),
                    'actual_hours': task_data.get('actual_hours'),
                    'planned_start': task_data.get('earliest_start'),
                    'planned_end': task_data.get('due_date'),
                    'assignees': assignees,
                    'predicted_delay_probability': task_data.get('predicted_delay_probability'),
                    'predicted_completion_date': task_data.get('predicted_completion_date')
                })
            
            # Sort by planned start
            timeline_items.sort(key=lambda x: x.get('planned_start') or '')
            
            # Calculate timeline metrics
            planned_start = project.data.get('planned_start')
            planned_end = project.data.get('planned_end')
            actual_start = project.data.get('actual_start')
            actual_end = project.data.get('actual_end')
            
            # Determine if on track
            status = 'on_track'
            if actual_end and planned_end:
                try:
                    actual = datetime.fromisoformat(actual_end.replace('Z', '+00:00'))
                    planned = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
                    if actual > planned:
                        status = 'delayed'
                except:
                    pass
            elif planned_end and datetime.utcnow() > datetime.fromisoformat(planned_end.replace('Z', '+00:00')):
                completed_count = sum(1 for t in timeline_items if t['status'] == 'done')
                if completed_count < len(timeline_items) * 0.9:
                    status = 'at_risk'
            
            return {
                'project_id': project_id,
                'project_name': project.data.get('name'),
                'timeline': {
                    'planned_start': planned_start,
                    'planned_end': planned_end,
                    'actual_start': actual_start,
                    'actual_end': actual_end
                },
                'status': status,
                'tasks': timeline_items,
                'summary': {
                    'total_tasks': len(timeline_items),
                    'completed': sum(1 for t in timeline_items if t['status'] == 'done'),
                    'in_progress': sum(1 for t in timeline_items if t['status'] == 'in_progress'),
                    'blocked': sum(1 for t in timeline_items if t['status'] == 'blocked'),
                    'at_risk': sum(1 for t in timeline_items if (t.get('predicted_delay_probability') or 0) > 0.7)
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get timeline", project_id=project_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get timeline: {str(e)}")
