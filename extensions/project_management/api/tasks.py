"""
Tasks API endpoints for Project Management.

Endpoints:
- GET /pm/tasks/{id}/matches - Best people for task
- GET /pm/tasks/{id}/dependencies - Dependency graph
- POST /pm/tasks/{id}/reassign - Reassign task
"""

from typing import Annotated, Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter, get_neo4j_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase
from ..agent_tools.analysis_tools import find_skill_matches
from ..agent_tools.action_tools import reassign_task

logger = get_logger(__name__)
router = APIRouter()


class ReassignRequest(BaseModel):
    """Request model for task reassignment."""
    to_person_id: str
    from_person_id: Optional[str] = None
    reason: Optional[str] = None


class ReassignResponse(BaseModel):
    """Response model for task reassignment."""
    success: bool
    task_id: str
    assignment_id: Optional[str]
    changes: Dict[str, Any]


@router.get("/{task_id}/matches")
async def get_task_skill_matches(
    task_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("task.read"))],
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Find the best people for a task based on skills.
    
    Returns:
        Skill match results with scores and recommendations
    """
    try:
        adapter = get_postgres_adapter()
        
        result = await find_skill_matches(adapter, task_id, limit=limit)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get matches", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get matches: {str(e)}")


@router.get("/{task_id}/dependencies")
async def get_task_dependencies(
    task_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("task.read"))],
) -> Dict[str, Any]:
    """
    Get dependency graph for a task.
    
    Returns:
        Tasks that block this task and tasks blocked by this task
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            task = base.get_object_by_id(session, task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Get tasks that block this task (prerequisites)
            blocking_links = base.get_linked_objects(
                session, task_id, link_type_id='lt_task_blocks'
            )
            
            # Note: We need to reverse lookup for tasks blocked BY this task
            # For now, query through Neo4j if available
            blocked_by_this = []
            
            if neo4j:
                try:
                    query = """
                    MATCH (t:Object {id: $task_id})<-[:lt_task_blocks]-(blocked:Object)
                    RETURN blocked.id as task_id, blocked.data as task_data
                    """
                    results = neo4j.execute_read(query, {'task_id': task_id})
                    blocked_by_this = [
                        {
                            'id': r['task_id'],
                            'title': r['task_data'].get('title', 'Unknown'),
                            'status': r['task_data'].get('status')
                        }
                        for r in results
                    ]
                except Exception as e:
                    logger.warning(f"Neo4j query failed: {e}")
            
            # Format blocking tasks
            blocked_by = []
            for link in blocking_links:
                blocker = link['object']
                blocked_by.append({
                    'id': blocker.id,
                    'title': blocker.data.get('title'),
                    'status': blocker.data.get('status'),
                    'dependency_type': link['link_data'].get('dependency_type', 'hard'),
                    'lag_days': link['link_data'].get('lag_days', 0)
                })
            
            # Check if on critical path (simplified)
            on_critical_path = len(blocked_by_this) > 2 or len(blocked_by) > 0
            
            return {
                'task_id': task_id,
                'task_title': task.data.get('title'),
                'dependencies': {
                    'blocked_by': blocked_by,
                    'blocked_by_count': len(blocked_by)
                },
                'dependents': {
                    'blocks': blocked_by_this,
                    'blocks_count': len(blocked_by_this)
                },
                'on_critical_path': on_critical_path,
                'can_start': all(b.get('status') == 'done' for b in blocked_by) if blocked_by else True
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get dependencies", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dependencies: {str(e)}")


@router.post("/{task_id}/reassign", response_model=ReassignResponse)
async def reassign_task_endpoint(
    task_id: Annotated[str, Path(...)],
    request: ReassignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("task.write"))],
) -> ReassignResponse:
    """
    Reassign a task to a different person.
    """
    try:
        adapter = get_postgres_adapter()
        
        result = await reassign_task(
            adapter,
            task_id=task_id,
            to_person_id=request.to_person_id,
            from_person_id=request.from_person_id,
            reason=request.reason
        )
        
        return ReassignResponse(
            success=result['success'],
            task_id=result['task_id'],
            assignment_id=result.get('assignment_id'),
            changes=result['changes']
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to reassign task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reassign: {str(e)}")
