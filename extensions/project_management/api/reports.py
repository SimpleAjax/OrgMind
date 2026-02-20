"""
Reports API endpoints for Project Management.

Endpoints:
- GET /pm/reports/portfolio - Portfolio report
- GET /pm/reports/utilization - Utilization report
- GET /pm/reports/skills - Skills gap report
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers.base import SchedulerBase
from ..schedulers import SkillMatcher, ConflictDetector
from ..agent_tools.query_tools import query_projects

logger = get_logger(__name__)
router = APIRouter()


@router.get("/portfolio")
async def get_portfolio_report(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("report.read"))],
    period: str = Query("monthly", description="Report period: weekly, monthly, quarterly"),
) -> Dict[str, Any]:
    """
    Get comprehensive portfolio report.
    
    Returns:
        Portfolio metrics, trends, and analysis
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            # Get all projects
            projects_result = await query_projects(adapter, limit=1000)
            projects = projects_result.get('projects', [])
            
            # Calculate metrics
            total_projects = len(projects)
            active = sum(1 for p in projects if p.get('status') == 'active')
            completed = sum(1 for p in projects if p.get('status') == 'completed')
            on_hold = sum(1 for p in projects if p.get('status') == 'on_hold')
            
            # Health distribution
            health_counts = {'green': 0, 'yellow': 0, 'red': 0}
            for p in projects:
                status = p.get('health_status', 'green')
                if status in health_counts:
                    health_counts[status] += 1
            
            # Priority distribution
            priority_buckets = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            for p in projects:
                score = p.get('priority_score', 50)
                if score >= 80:
                    priority_buckets['critical'] += 1
                elif score >= 60:
                    priority_buckets['high'] += 1
                elif score >= 40:
                    priority_buckets['medium'] += 1
                else:
                    priority_buckets['low'] += 1
            
            # Timeline analysis
            overdue = []
            at_risk = []
            
            for p in projects:
                planned_end = p.get('planned_end')
                if planned_end and p.get('status') == 'active':
                    try:
                        end = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
                        if end < datetime.utcnow():
                            overdue.append({
                                'id': p['id'],
                                'name': p['name'],
                                'days_overdue': (datetime.utcnow() - end).days
                            })
                        elif (end - datetime.utcnow()).days < 14:
                            at_risk.append({
                                'id': p['id'],
                                'name': p['name'],
                                'days_remaining': (end - datetime.utcnow()).days
                            })
                    except:
                        pass
            
            # Sort by severity
            overdue.sort(key=lambda x: x['days_overdue'], reverse=True)
            at_risk.sort(key=lambda x: x['days_remaining'])
            
            return {
                'report_type': 'portfolio',
                'period': period,
                'generated_at': datetime.utcnow().isoformat(),
                'summary': {
                    'total_projects': total_projects,
                    'active': active,
                    'completed': completed,
                    'on_hold': on_hold,
                    'completion_rate': round(completed / total_projects * 100, 2) if total_projects > 0 else 0
                },
                'health_summary': health_counts,
                'priority_distribution': priority_buckets,
                'timeline': {
                    'overdue_count': len(overdue),
                    'at_risk_count': len(at_risk),
                    'overdue_projects': overdue[:10],
                    'at_risk_projects': at_risk[:10]
                },
                'risk_indicators': {
                    'high_risk_projects': sum(1 for p in projects if p.get('risk_score', 0) > 70),
                    'avg_risk_score': round(sum(p.get('risk_score', 0) for p in projects) / len(projects), 2) if projects else 0
                }
            }
            
    except Exception as e:
        logger.error("Failed to generate portfolio report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/utilization")
async def get_utilization_report(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("report.read"))],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    Get resource utilization report.
    
    Returns:
        Utilization metrics across all resources
    """
    try:
        adapter = get_postgres_adapter()
        base = SchedulerBase(adapter)
        
        with base.get_session() as session:
            # Get all active people
            people = base.get_objects_by_type(session, 'ot_person', status='active')
            
            utilization_data = []
            total_capacity = 0
            total_allocated = 0
            
            for person in people:
                from ..agent_tools.query_tools import get_person_utilization
                
                try:
                    util = await get_person_utilization(
                        adapter,
                        person.id,
                        date_range={'start': start_date, 'end': end_date}
                    )
                    
                    utilization_data.append({
                        'person_id': person.id,
                        'name': person.data.get('name'),
                        'role': person.data.get('role'),
                        'average_utilization': util['utilization']['average'],
                        'max_utilization': util['utilization']['maximum'],
                        'status': util['status'],
                        'assignment_count': len(util['current_assignments'])
                    })
                    
                    # Calculate totals (simplified)
                    capacity = sum(
                        a.get('planned_hours', 0)
                        for a in util['current_assignments']
                    )
                    total_capacity += capacity
                    
                except Exception as e:
                    logger.warning(f"Failed to get utilization for {person.id}: {e}")
            
            # Calculate statistics
            if utilization_data:
                avg_util = sum(u['average_utilization'] for u in utilization_data) / len(utilization_data)
                overallocated = [u for u in utilization_data if u['status'] == 'overallocated']
                underutilized = [u for u in utilization_data if u['average_utilization'] < 50]
                optimal = [u for u in utilization_data if 50 <= u['average_utilization'] <= 100]
            else:
                avg_util = 0
                overallocated = []
                underutilized = []
                optimal = []
            
            return {
                'report_type': 'utilization',
                'period': {'start': start_date, 'end': end_date},
                'generated_at': datetime.utcnow().isoformat(),
                'summary': {
                    'total_resources': len(utilization_data),
                    'average_utilization': round(avg_util, 2),
                    'overallocated_count': len(overallocated),
                    'underutilized_count': len(underutilized),
                    'optimal_count': len(optimal)
                },
                'distribution': {
                    'overallocated': overallocated,
                    'underutilized': underutilized,
                    'optimal': optimal
                },
                'utilization_by_role': _group_by_role(utilization_data),
                'trend': 'stable'  # Would calculate from historical data
            }
            
    except Exception as e:
        logger.error("Failed to generate utilization report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/skills")
async def get_skills_gap_report(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("report.read"))],
) -> Dict[str, Any]:
    """
    Get skills gap report.
    
    Returns:
        Organization-wide skills analysis and gaps
    """
    try:
        adapter = get_postgres_adapter()
        matcher = SkillMatcher(adapter)
        
        # Identify skill gaps
        gaps = await matcher.identify_skill_gaps()
        
        # Format gaps
        formatted_gaps = []
        for gap in gaps:
            formatted_gaps.append({
                'skill_id': gap.skill_id,
                'skill_name': gap.skill_name,
                'category': gap.skill_category,
                'severity': gap.gap_severity,
                'tasks_requiring': gap.tasks_requiring,
                'qualified_people': gap.qualified_people,
                'ratio': round(gap.tasks_requiring / gap.qualified_people, 2) if gap.qualified_people > 0 else float('inf'),
                'training_suggestions': gap.training_suggestions[:3]
            })
        
        # Calculate summary
        critical = sum(1 for g in formatted_gaps if g['severity'] == 'critical')
        high = sum(1 for g in formatted_gaps if g['severity'] == 'high')
        medium = sum(1 for g in formatted_gaps if g['severity'] == 'medium')
        
        # Top gaps by severity
        top_gaps = [g for g in formatted_gaps if g['severity'] in ['critical', 'high']][:10]
        
        return {
            'report_type': 'skills_gap',
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {
                'total_skills_analyzed': len(formatted_gaps),
                'critical_gaps': critical,
                'high_gaps': high,
                'medium_gaps': medium,
                'gaps_with_no_coverage': sum(1 for g in formatted_gaps if g['qualified_people'] == 0)
            },
            'top_gaps': top_gaps,
            'all_gaps': formatted_gaps,
            'recommendations': [
                f"Address {critical} critical skill gaps immediately",
                f"Schedule training for {high} high-priority skills",
                "Consider hiring for skills with zero coverage"
            ] if critical > 0 or high > 0 else ["Skills coverage is adequate"]
        }
        
    except Exception as e:
        logger.error("Failed to generate skills report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


def _group_by_role(utilization_data: List[Dict]) -> Dict[str, Dict]:
    """Group utilization data by role."""
    by_role = {}
    
    for u in utilization_data:
        role = u.get('role', 'other')
        if role not in by_role:
            by_role[role] = {
                'count': 0,
                'total_utilization': 0,
                'overallocated': 0
            }
        
        by_role[role]['count'] += 1
        by_role[role]['total_utilization'] += u['average_utilization']
        if u['status'] == 'overallocated':
            by_role[role]['overallocated'] += 1
    
    # Calculate averages
    for role in by_role:
        by_role[role]['average_utilization'] = round(
            by_role[role]['total_utilization'] / by_role[role]['count'], 2
        )
        del by_role[role]['total_utilization']
    
    return by_role
