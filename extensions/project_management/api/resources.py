"""
Resources API endpoints for Project Management.

Endpoints:
- GET /pm/resources/allocations - All allocations
- GET /pm/resources/{id}/utilization - Single person view
- GET /pm/resources/conflicts - Current conflicts
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase
from ..schedulers import ConflictDetector
from ..agent_tools.query_tools import get_person_utilization

logger = get_logger(__name__)
router = APIRouter()


@router.get("/allocations")
async def get_all_allocations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("resource.read"))],
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    person_id: Optional[str] = Query(None, description="Filter by person"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
) -> Dict[str, Any]:
    """
    Get all resource allocations.
    
    Returns:
        List of all assignments with person and task details
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            from sqlalchemy import select, and_
            from orgmind.storage.models import ObjectModel
            
            stmt = select(ObjectModel).where(
                and_(
                    ObjectModel.type_id == 'ot_assignment',
                    ObjectModel.status == 'active'
                )
            )
            
            assignments = session.scalars(stmt).all()
            
            allocations = []
            for assignment in assignments:
                data = assignment.data
                
                # Filter by person if specified
                if person_id and data.get('person_id') != person_id:
                    continue
                
                # Get person details
                person = base.get_object_by_id(session, data.get('person_id'))
                if not person:
                    continue
                
                # Get task details
                task = base.get_object_by_id(session, data.get('task_id'))
                if not task:
                    continue
                
                # Filter by project if specified
                task_project_id = task.data.get('project_id')
                if project_id and task_project_id != project_id:
                    continue
                
                # Date filtering
                assignment_start = data.get('planned_start', '')
                assignment_end = data.get('planned_end', '')
                
                if date_from and assignment_end and assignment_end < date_from:
                    continue
                if date_to and assignment_start and assignment_start > date_to:
                    continue
                
                allocations.append({
                    'assignment_id': assignment.id,
                    'person': {
                        'id': person.id,
                        'name': person.data.get('name'),
                        'role': person.data.get('role')
                    },
                    'task': {
                        'id': task.id,
                        'title': task.data.get('title'),
                        'project_id': task_project_id
                    },
                    'allocation': {
                        'percent': data.get('allocation_percent', 100),
                        'planned_hours': data.get('planned_hours'),
                        'actual_hours': data.get('actual_hours'),
                        'start': assignment_start,
                        'end': assignment_end,
                        'status': data.get('status')
                    }
                })
            
            return {
                'count': len(allocations),
                'allocations': allocations,
                'generated_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get allocations", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get allocations: {str(e)}")


@router.get("/{person_id}/utilization")
async def get_person_utilization_endpoint(
    person_id: Annotated[str, Path(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("resource.read"))],
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    Get detailed utilization for a specific person.
    
    Returns:
        Utilization metrics and assignment breakdown
    """
    try:
        adapter = get_postgres_adapter()
        
        # Default to next 30 days if no dates provided
        if not start_date:
            start_date = datetime.utcnow().strftime('%Y-%m-%d')
        if not end_date:
            end_date = (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        result = await get_person_utilization(
            adapter,
            person_id,
            date_range={'start': start_date, 'end': end_date}
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get utilization", person_id=person_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get utilization: {str(e)}")


@router.get("/conflicts")
async def get_resource_conflicts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("resource.read"))],
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low"),
    conflict_type: Optional[str] = Query(None, description="Filter by type: overallocation, double_booking, skill_mismatch"),
) -> Dict[str, Any]:
    """
    Get current resource conflicts.
    
    Returns:
        List of detected conflicts with suggested resolutions
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        detector = ConflictDetector(adapter, neo4j)
        
        # Run conflict detection
        summary = await detector.detect_conflicts()
        
        # Filter by severity if specified
        conflicts = []
        for conflict in summary.critical_issues:
            if severity and conflict.severity.value != severity:
                continue
            if conflict_type and conflict.conflict_type.value != conflict_type:
                continue
            conflicts.append({
                'type': conflict.conflict_type.value,
                'severity': conflict.severity.value,
                'description': conflict.description,
                'person_id': conflict.person_id,
                'person_name': conflict.person_name,
                'task_id': conflict.task_id,
                'sprint_id': conflict.sprint_id,
                'date_range': conflict.date_range,
                'allocation_percentage': conflict.allocation_percentage,
                'suggested_actions': conflict.suggested_actions,
                'detected_at': conflict.detected_at
            })
        
        # Also include non-critical if not filtering by severity
        if severity != 'critical':
            # Run full detection to get all conflicts
            # Note: This is simplified - in production, you'd want to cache results
            all_overallocations = await detector.detect_overallocations()
            all_mismatches = await detector.detect_skill_mismatches()
            
            for conflict in all_overallocations + all_mismatches:
                if severity and conflict.severity.value != severity:
                    continue
                if conflict_type and conflict.conflict_type.value != conflict_type:
                    continue
                
                # Avoid duplicates
                if not any(c['description'] == conflict.description for c in conflicts):
                    conflicts.append({
                        'type': conflict.conflict_type.value,
                        'severity': conflict.severity.value,
                        'description': conflict.description,
                        'person_id': conflict.person_id,
                        'person_name': conflict.person_name,
                        'task_id': conflict.task_id,
                        'sprint_id': conflict.sprint_id,
                        'date_range': conflict.date_range,
                        'allocation_percentage': conflict.allocation_percentage,
                        'suggested_actions': conflict.suggested_actions,
                        'detected_at': conflict.detected_at
                    })
        
        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        conflicts.sort(key=lambda x: severity_order.get(x['severity'], 4))
        
        return {
            'summary': {
                'total_conflicts': len(conflicts),
                'critical': sum(1 for c in conflicts if c['severity'] == 'critical'),
                'high': sum(1 for c in conflicts if c['severity'] == 'high'),
                'medium': sum(1 for c in conflicts if c['severity'] == 'medium'),
                'low': sum(1 for c in conflicts if c['severity'] == 'low')
            },
            'conflicts': conflicts,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get conflicts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get conflicts: {str(e)}")
