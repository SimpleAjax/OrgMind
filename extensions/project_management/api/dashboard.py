"""
Dashboard API endpoints for Project Management.

Endpoints:
- GET /pm/dashboard/portfolio - Portfolio overview
- GET /pm/dashboard/risks - At-risk items
- GET /pm/dashboard/utilization - Resource heatmap
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter, get_neo4j_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase
from ..schedulers import PriorityCalculator, NudgeGenerator, ConflictDetector
from ..agent_tools.query_tools import query_projects, get_project_health

logger = get_logger(__name__)
router = APIRouter()


@router.get("/portfolio")
async def get_portfolio_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
    status: Optional[str] = Query(None, description="Filter by project status"),
    limit: int = Query(50, ge=1, le=100),
) -> Dict[str, Any]:
    """
    Get portfolio overview with project summaries.
    
    Returns:
        Portfolio metrics including project statuses, health scores, and risk indicators
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            # Get projects
            filter_criteria = {'status': status} if status else {}
            projects_result = await query_projects(adapter, filter=filter_criteria, limit=limit)
            
            projects = projects_result.get('projects', [])
            
            # Calculate portfolio metrics
            total_projects = len(projects)
            active_projects = sum(1 for p in projects if p.get('status') == 'active')
            at_risk_projects = sum(1 for p in projects if p.get('health_status') == 'red')
            warning_projects = sum(1 for p in projects if p.get('health_status') == 'yellow')
            
            # Priority distribution
            high_priority = sum(1 for p in projects if p.get('priority_score', 0) >= 75)
            
            # Timeline metrics
            overdue_projects = []
            for project in projects:
                planned_end = project.get('planned_end')
                if planned_end:
                    try:
                        end_date = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
                        if end_date < datetime.utcnow() and project.get('status') != 'completed':
                            overdue_projects.append({
                                'id': project['id'],
                                'name': project['name'],
                                'days_overdue': (datetime.utcnow() - end_date).days
                            })
                    except:
                        pass
            
            return {
                'summary': {
                    'total_projects': total_projects,
                    'active_projects': active_projects,
                    'at_risk_count': at_risk_projects,
                    'warning_count': warning_projects,
                    'healthy_count': total_projects - at_risk_projects - warning_projects,
                    'high_priority_count': high_priority,
                    'overdue_count': len(overdue_projects)
                },
                'health_distribution': {
                    'excellent': sum(1 for p in projects if p.get('health_status') == 'green'),
                    'at_risk': warning_projects,
                    'critical': at_risk_projects
                },
                'projects': projects,
                'overdue_projects': overdue_projects[:5],  # Top 5 most overdue
                'generated_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get portfolio overview", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio: {str(e)}")


@router.get("/risks")
async def get_risk_dashboard(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low"),
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    """
    Get at-risk items dashboard.
    
    Returns:
        Tasks and projects with risk indicators
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        risks = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        with base.get_session() as session:
            # Get at-risk tasks
            from ..agent_tools.query_tools import query_tasks
            
            tasks_result = await query_tasks(
                adapter,
                filter={'predicted_delay_min': 0.5},  # 50% delay probability
                limit=100
            )
            
            for task in tasks_result.get('tasks', []):
                delay_prob = task.get('predicted_delay_probability', 0)
                
                if delay_prob >= 0.9:
                    severity_level = 'critical'
                elif delay_prob >= 0.75:
                    severity_level = 'high'
                elif delay_prob >= 0.5:
                    severity_level = 'medium'
                else:
                    severity_level = 'low'
                
                risk_item = {
                    'type': 'task',
                    'id': task['id'],
                    'title': task['title'],
                    'project_id': task.get('project_id'),
                    'risk_score': delay_prob * 100,
                    'due_date': task.get('due_date'),
                    'reason': f"{delay_prob*100:.0f}% delay probability"
                }
                
                risks[severity_level].append(risk_item)
            
            # Get at-risk projects
            projects_result = await query_projects(adapter, limit=50)
            for project in projects_result.get('projects', []):
                risk_score = project.get('risk_score', 0)
                
                if risk_score >= 75:
                    severity_level = 'critical'
                elif risk_score >= 50:
                    severity_level = 'high'
                elif risk_score >= 25:
                    severity_level = 'medium'
                else:
                    continue  # Skip low risk projects
                
                if severity and severity_level != severity:
                    continue
                
                risk_item = {
                    'type': 'project',
                    'id': project['id'],
                    'name': project['name'],
                    'risk_score': risk_score,
                    'health_status': project.get('health_status'),
                    'reason': f"Risk score: {risk_score:.0f}"
                }
                
                risks[severity_level].append(risk_item)
            
            # Filter and limit
            if severity:
                result = {severity: risks[severity][:limit]}
            else:
                result = {
                    'critical': risks['critical'][:limit],
                    'high': risks['high'][:limit],
                    'medium': risks['medium'][:limit]
                }
            
            return {
                'risk_summary': {
                    'critical_count': len(risks['critical']),
                    'high_count': len(risks['high']),
                    'medium_count': len(risks['medium']),
                    'total': len(risks['critical']) + len(risks['high']) + len(risks['medium'])
                },
                'risks': result,
                'generated_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get risk dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get risks: {str(e)}")


@router.get("/utilization")
async def get_utilization_heatmap(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("resource.read"))],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    Get resource utilization heatmap.
    
    Returns:
        Daily utilization data for all resources
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            # Get all active people
            people = base.get_objects_by_type(session, 'ot_person', status='active')
            
            utilization_data = []
            
            for person in people:
                from ..agent_tools.query_tools import get_person_utilization
                
                util_result = await get_person_utilization(
                    adapter,
                    person.id,
                    date_range={'start': start_date, 'end': end_date}
                )
                
                utilization_data.append({
                    'person_id': person.id,
                    'person_name': person.data.get('name'),
                    'role': person.data.get('role'),
                    'average_utilization': util_result['utilization']['average'],
                    'max_utilization': util_result['utilization']['maximum'],
                    'status': util_result['status'],
                    'assignment_count': len(util_result['current_assignments'])
                })
            
            # Sort by utilization (highest first)
            utilization_data.sort(key=lambda x: x['max_utilization'], reverse=True)
            
            # Calculate summary
            avg_util = sum(u['average_utilization'] for u in utilization_data) / len(utilization_data) if utilization_data else 0
            overallocated = sum(1 for u in utilization_data if u['status'] == 'overallocated')
            underutilized = sum(1 for u in utilization_data if u['average_utilization'] < 50)
            
            return {
                'summary': {
                    'total_resources': len(utilization_data),
                    'average_utilization': round(avg_util, 2),
                    'overallocated_count': overallocated,
                    'underutilized_count': underutilized,
                    'optimal_count': len(utilization_data) - overallocated - underutilized
                },
                'utilization': utilization_data,
                'date_range': {'start': start_date, 'end': end_date},
                'generated_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get utilization", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get utilization: {str(e)}")
