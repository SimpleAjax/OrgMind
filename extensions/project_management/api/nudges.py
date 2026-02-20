"""
Nudges API endpoints for Project Management.

Endpoints:
- GET /pm/nudges - List nudges
- POST /pm/nudges/{id}/acknowledge - Acknowledge nudge
- POST /pm/nudges/{id}/dismiss - Dismiss nudge
- POST /pm/nudges/{id}/act - Execute suggested action
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase

logger = get_logger(__name__)
router = APIRouter()


class NudgeActionRequest(BaseModel):
    """Request model for executing nudge action."""
    action_index: int = 0  # Index of suggested action to execute
    parameters: Optional[Dict[str, Any]] = None  # Custom parameters


class NudgeResponse(BaseModel):
    """Response model for nudge operations."""
    success: bool
    nudge_id: str
    new_status: str
    message: str


@router.get("/")
async def list_nudges(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("nudge.read"))],
    status: Optional[str] = Query(None, description="Filter by status: new, acknowledged, resolved, dismissed"),
    type: Optional[str] = Query(None, description="Filter by type: risk, opportunity, conflict, suggestion"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical"),
    for_me: bool = Query(True, description="Only show nudges for current user"),
    limit: int = Query(50, ge=1, le=100),
) -> Dict[str, Any]:
    """
    List nudges with optional filters.
    
    Returns:
        List of nudges matching criteria
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            from sqlalchemy import select, and_, or_
            from orgmind.storage.models import ObjectModel
            
            stmt = select(ObjectModel).where(
                ObjectModel.type_id == 'ot_nudge'
            )
            
            # Apply filters
            if status:
                stmt = stmt.where(
                    ObjectModel.data['status'].astext == status
                )
            else:
                # Default to active nudges
                stmt = stmt.where(
                    ObjectModel.data['status'].astext.in_(['new', 'acknowledged'])
                )
            
            if type:
                stmt = stmt.where(
                    ObjectModel.data['type'].astext == type
                )
            
            if severity:
                stmt = stmt.where(
                    ObjectModel.data['severity'].astext == severity
                )
            
            # Filter for current user
            if for_me:
                stmt = stmt.where(
                    ObjectModel.data['recipient_id'].astext == current_user.id
                )
            
            stmt = stmt.order_by(ObjectModel.created_at.desc()).limit(limit)
            
            nudges = session.scalars(stmt).all()
            
            results = []
            for nudge in nudges:
                data = nudge.data
                
                results.append({
                    'id': nudge.id,
                    'type': data.get('type'),
                    'severity': data.get('severity'),
                    'title': data.get('title'),
                    'description': data.get('description'),
                    'status': data.get('status'),
                    'recipient_id': data.get('recipient_id'),
                    'related_project_id': data.get('related_project_id'),
                    'related_task_id': data.get('related_task_id'),
                    'related_person_id': data.get('related_person_id'),
                    'context_data': data.get('context_data'),
                    'ai_confidence': data.get('ai_confidence'),
                    'created_at': nudge.created_at.isoformat() if nudge.created_at else None,
                    'acknowledged_at': data.get('acknowledged_at'),
                    'resolved_at': data.get('resolved_at')
                })
            
            # Group by status for summary
            by_status = {}
            for n in results:
                s = n['status']
                by_status[s] = by_status.get(s, 0) + 1
            
            return {
                'count': len(results),
                'by_status': by_status,
                'nudges': results
            }
            
    except Exception as e:
        logger.error("Failed to list nudges", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list nudges: {str(e)}")


@router.post("/{nudge_id}/acknowledge", response_model=NudgeResponse)
async def acknowledge_nudge(
    nudge_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("nudge.write"))],
) -> NudgeResponse:
    """
    Acknowledge a nudge (mark as seen but not resolved).
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            nudge = base.get_object_by_id(session, nudge_id)
            if not nudge:
                raise HTTPException(status_code=404, detail="Nudge not found")
            
            # Verify ownership
            if nudge.data.get('recipient_id') != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to acknowledge this nudge")
            
            # Update status
            nudge.data['status'] = 'acknowledged'
            nudge.data['acknowledged_at'] = datetime.utcnow().isoformat()
            nudge.data['acknowledged_by'] = current_user.id
            nudge.version += 1
            
            session.commit()
            
            return NudgeResponse(
                success=True,
                nudge_id=nudge_id,
                new_status='acknowledged',
                message="Nudge acknowledged"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge nudge", nudge_id=nudge_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge: {str(e)}")


@router.post("/{nudge_id}/dismiss", response_model=NudgeResponse)
async def dismiss_nudge(
    nudge_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("nudge.write"))],
    reason: Optional[str] = None,
) -> NudgeResponse:
    """
    Dismiss a nudge (mark as no longer relevant).
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            nudge = base.get_object_by_id(session, nudge_id)
            if not nudge:
                raise HTTPException(status_code=404, detail="Nudge not found")
            
            # Verify ownership
            if nudge.data.get('recipient_id') != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to dismiss this nudge")
            
            # Update status
            nudge.data['status'] = 'dismissed'
            nudge.data['dismissed_at'] = datetime.utcnow().isoformat()
            nudge.data['dismissed_by'] = current_user.id
            nudge.data['dismissed_reason'] = reason or 'User dismissed'
            nudge.version += 1
            
            session.commit()
            
            return NudgeResponse(
                success=True,
                nudge_id=nudge_id,
                new_status='dismissed',
                message="Nudge dismissed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to dismiss nudge", nudge_id=nudge_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to dismiss: {str(e)}")


@router.post("/{nudge_id}/act")
async def execute_nudge_action(
    nudge_id: Annotated[str, Path(...)],
    request: NudgeActionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("nudge.write"))],
) -> Dict[str, Any]:
    """
    Execute a suggested action from a nudge.
    
    This performs the recommended action (e.g., reassign task, extend deadline).
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            nudge = base.get_object_by_id(session, nudge_id)
            if not nudge:
                raise HTTPException(status_code=404, detail="Nudge not found")
            
            # Verify ownership
            if nudge.data.get('recipient_id') != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to act on this nudge")
            
            # Get suggested actions
            # In a real implementation, these would be stored in nudge actions
            # For now, we'll infer from context
            
            action_result = None
            action_type = None
            
            # Check for related task
            related_task_id = nudge.data.get('related_task_id')
            related_person_id = nudge.data.get('related_person_id')
            
            if related_task_id and request.action_index == 0:
                # Default action: reassign if there's a person issue
                if related_person_id and nudge.data.get('type') == 'conflict':
                    from ..agent_tools.action_tools import find_skill_matches
                    
                    # Find alternative
                    matches = await find_skill_matches(adapter, related_task_id, limit=1)
                    if matches.get('matches'):
                        best_match = matches['matches'][0]
                        
                        from ..agent_tools.action_tools import reassign_task
                        
                        action_result = await reassign_task(
                            adapter,
                            task_id=related_task_id,
                            to_person_id=best_match['person_id'],
                            from_person_id=related_person_id,
                            reason=f"Auto-reassigned from nudge: {nudge.data.get('title')}"
                        )
                        action_type = 'reassign'
            
            # Mark nudge as resolved
            nudge.data['status'] = 'resolved'
            nudge.data['resolved_at'] = datetime.utcnow().isoformat()
            nudge.data['resolved_by'] = current_user.id
            nudge.data['action_taken'] = action_type or 'manual'
            nudge.version += 1
            
            session.commit()
            
            return {
                'success': True,
                'nudge_id': nudge_id,
                'new_status': 'resolved',
                'action_type': action_type,
                'action_result': action_result,
                'message': f"Action executed: {action_type or 'manual resolution'}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to execute nudge action", nudge_id=nudge_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to execute action: {str(e)}")
