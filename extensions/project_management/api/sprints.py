"""
Sprints API endpoints for Project Management.

Endpoints:
- GET /pm/sprints/{id}/recommendations - AI recommendations
- POST /pm/sprints/{id}/plan - Commit sprint plan
- GET /pm/sprints/{id}/health - Sprint health check
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

from ..schedulers import SprintPlanner
from ..schedulers.base import SchedulerBase
from ..agent_tools.analysis_tools import get_sprint_recommendations

logger = get_logger(__name__)
router = APIRouter()


class SprintPlanRequest(BaseModel):
    """Request model for committing sprint plan."""
    task_ids: List[str]
    assignments: Optional[Dict[str, str]] = None  # task_id -> person_id


class SprintPlanResponse(BaseModel):
    """Response model for sprint plan commit."""
    success: bool
    sprint_id: str
    tasks_committed: int
    warnings: List[str]


@router.get("/{sprint_id}/recommendations")
async def get_sprint_recommendations_endpoint(
    sprint_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("sprint.read"))],
) -> Dict[str, Any]:
    """
    Get AI recommendations for sprint planning.
    
    Returns:
        Recommended tasks, load distribution, and risk assessment
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        result = await get_sprint_recommendations(adapter, neo4j, sprint_id)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get recommendations", sprint_id=sprint_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.post("/{sprint_id}/plan", response_model=SprintPlanResponse)
async def commit_sprint_plan(
    sprint_id: Annotated[str, Path(...)],
    request: SprintPlanRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("sprint.write"))],
) -> SprintPlanResponse:
    """
    Commit a sprint plan by adding tasks to the sprint.
    
    This creates SprintTask junction records and optionally creates assignments.
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        warnings = []
        committed_count = 0
        
        with base.get_session() as session:
            # Verify sprint exists
            sprint = base.get_object_by_id(session, sprint_id)
            if not sprint:
                raise HTTPException(status_code=404, detail="Sprint not found")
            
            # Add each task to sprint
            for task_id in request.task_ids:
                task = base.get_object_by_id(session, task_id)
                if not task:
                    warnings.append(f"Task {task_id} not found")
                    continue
                
                # Check if already in sprint
                from sqlalchemy import select, and_
                from orgmind.storage.models import ObjectModel, LinkModel
                import uuid
                
                existing = session.scalar(
                    select(ObjectModel).where(
                        and_(
                            ObjectModel.type_id == 'ot_sprint_task',
                            ObjectModel.data['sprint_id'].astext == sprint_id,
                            ObjectModel.data['task_id'].astext == task_id
                        )
                    )
                )
                
                if existing:
                    warnings.append(f"Task {task_id} already in sprint")
                    continue
                
                # Create SprintTask junction
                sprint_task = ObjectModel(
                    id=str(uuid.uuid4()),
                    type_id='ot_sprint_task',
                    data={
                        'sprint_id': sprint_id,
                        'task_id': task_id,
                        'status': 'todo',
                        'added_at': datetime.utcnow().isoformat()
                    },
                    status='active'
                )
                session.add(sprint_task)
                
                # Create assignment if specified
                if request.assignments and task_id in request.assignments:
                    person_id = request.assignments[task_id]
                    
                    # Check for existing assignment
                    existing_assign = session.scalar(
                        select(ObjectModel).where(
                            and_(
                                ObjectModel.type_id == 'ot_assignment',
                                ObjectModel.data['task_id'].astext == task_id,
                                ObjectModel.status == 'active'
                            )
                        )
                    )
                    
                    if existing_assign:
                        # Update existing assignment
                        existing_assign.data['person_id'] = person_id
                        existing_assign.data['updated_at'] = datetime.utcnow().isoformat()
                    else:
                        # Create new assignment
                        assignment = ObjectModel(
                            id=str(uuid.uuid4()),
                            type_id='ot_assignment',
                            data={
                                'person_id': person_id,
                                'task_id': task_id,
                                'allocation_percent': 100,
                                'role_in_task': 'primary',
                                'planned_start': sprint.data.get('start_date'),
                                'planned_end': sprint.data.get('end_date'),
                                'planned_hours': task.data.get('estimated_hours', 8),
                                'status': 'planned'
                            },
                            status='active'
                        )
                        session.add(assignment)
                
                committed_count += 1
            
            # Update sprint committed hours
            if committed_count > 0:
                total_hours = sum(
                    t.data.get('estimated_hours', 0)
                    for t in [base.get_object_by_id(session, tid) for tid in request.task_ids]
                    if t
                )
                
                current_committed = sprint.data.get('committed_hours', 0)
                sprint.data['committed_hours'] = current_committed + total_hours
                sprint.version += 1
            
            session.commit()
            
            return SprintPlanResponse(
                success=True,
                sprint_id=sprint_id,
                tasks_committed=committed_count,
                warnings=warnings
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to commit sprint plan", sprint_id=sprint_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to commit plan: {str(e)}")


@router.get("/{sprint_id}/health")
async def get_sprint_health_endpoint(
    sprint_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("sprint.read"))],
) -> Dict[str, Any]:
    """
    Get comprehensive health check for a sprint.
    
    Returns:
        Health metrics, completion rate, and predictions
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        planner = SprintPlanner(adapter, neo4j)
        health = await planner.check_sprint_health(sprint_id)
        
        return {
            'sprint_id': health.sprint_id,
            'status': health.status.value,
            'health_score': health.health_score,
            'progress': {
                'completion_percentage': health.completion_percentage,
                'committed_hours': health.committed_hours,
                'completed_hours': health.completed_hours,
                'remaining_capacity': health.remaining_capacity
            },
            'issues': {
                'blocked_tasks': health.blocked_tasks_count,
                'at_risk_tasks': health.at_risk_tasks_count,
                'scope_changes': health.scope_change_count,
                'overallocations': health.overallocation_count
            },
            'predictions': {
                'completion_rate': health.predicted_completion_rate,
                'predicted_end_date': health.predicted_end_date
            },
            'team_utilization': health.team_utilization,
            'recommendations': health.recommendations,
            'detailed_issues': health.issues,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get sprint health", sprint_id=sprint_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health: {str(e)}")
