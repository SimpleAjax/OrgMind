"""
Simulation API endpoints for Project Management.

Endpoints:
- POST /pm/simulate/leave - Simulate person on leave
- POST /pm/simulate/scope - Simulate scope change
- POST /pm/simulate/compare - Compare scenarios
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_db, get_postgres_adapter, get_neo4j_adapter
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

from ..schedulers import ImpactAnalyzer

logger = get_logger(__name__)
router = APIRouter()


class LeaveSimulationRequest(BaseModel):
    """Request model for leave simulation."""
    person_id: str
    start_date: str  # ISO format
    end_date: str    # ISO format
    leave_type: str = "vacation"  # vacation, sick, training


class ScopeSimulationRequest(BaseModel):
    """Request model for scope change simulation."""
    project_id: str
    added_tasks: Optional[List[Dict[str, Any]]] = None
    removed_task_ids: Optional[List[str]] = None


class CompareScenariosRequest(BaseModel):
    """Request model for comparing scenarios."""
    scenarios: List[Dict[str, Any]]  # List of scenario definitions


@router.post("/leave")
async def simulate_leave(
    request: LeaveSimulationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
) -> Dict[str, Any]:
    """
    Simulate the impact of a person going on leave.
    
    Returns:
        Impact analysis with affected tasks and recommended actions
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        analyzer = ImpactAnalyzer(adapter, neo4j)
        
        report = await analyzer.analyze_leave_impact(
            person_id=request.person_id,
            start_date=request.start_date,
            end_date=request.end_date,
            leave_type=request.leave_type
        )
        
        return {
            'simulation_type': 'leave',
            'parameters': {
                'person_id': request.person_id,
                'person_name': report.parameters.get('person_name'),
                'start_date': request.start_date,
                'end_date': request.end_date,
                'leave_type': request.leave_type
            },
            'impact': {
                'level': report.impact_level.value,
                'summary': report.summary,
                'affected_projects': report.affected_projects,
                'affected_tasks_count': len(report.affected_tasks),
                'total_delay_days': report.total_delay_days
            },
            'affected_tasks': report.affected_tasks,
            'alternative_resources': report.alternative_resources,
            'recommended_actions': report.recommended_actions,
            'cost_impact': report.cost_impact,
            'can_mitigate': len(report.alternative_resources) > 0,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to simulate leave", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to simulate: {str(e)}")


@router.post("/scope")
async def simulate_scope_change(
    request: ScopeSimulationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
) -> Dict[str, Any]:
    """
    Simulate the impact of adding or removing tasks from a project.
    
    Returns:
        Impact analysis with timeline and resource impact
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        analyzer = ImpactAnalyzer(adapter, neo4j)
        
        report = await analyzer.analyze_scope_change_impact(
            project_id=request.project_id,
            added_tasks=request.added_tasks or [],
            removed_tasks=request.removed_task_ids or []
        )
        
        return {
            'simulation_type': 'scope_change',
            'parameters': {
                'project_id': request.project_id,
                'project_name': report.affected_projects[0].get('project_name') if report.affected_projects else 'Unknown',
                'tasks_added': len(request.added_tasks or []),
                'tasks_removed': len(request.removed_task_ids or [])
            },
            'impact': {
                'level': report.impact_level.value,
                'summary': report.summary,
                'timeline_delay_days': report.timeline_changes.get('delay_days', 0),
                'resource_conflicts': len(report.resource_conflicts)
            },
            'current_state': {
                'total_hours': report.affected_projects[0].get('current_hours') if report.affected_projects else 0
            },
            'projected_state': {
                'total_hours': report.affected_projects[0].get('new_hours') if report.affected_projects else 0
            },
            'timeline_changes': report.timeline_changes,
            'resource_conflicts': report.resource_conflicts,
            'cost_impact': report.cost_impact,
            'recommended_actions': report.recommended_actions,
            'can_commit': report.impact_level.value != 'critical',
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to simulate scope change", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to simulate: {str(e)}")


@router.post("/compare")
async def compare_scenarios(
    request: CompareScenariosRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("project.read"))],
) -> Dict[str, Any]:
    """
    Compare multiple scenarios side-by-side.
    
    Returns:
        Comparison of different scenarios with pros/cons
    """
    try:
        adapter = get_postgres_adapter()
        neo4j = get_neo4j_adapter()
        
        analyzer = ImpactAnalyzer(adapter, neo4j)
        
        scenario_results = []
        
        for i, scenario in enumerate(request.scenarios):
            scenario_type = scenario.get('type')
            params = scenario.get('parameters', {})
            
            try:
                if scenario_type == 'leave':
                    report = await analyzer.analyze_leave_impact(**params)
                elif scenario_type == 'scope_change':
                    report = await analyzer.analyze_scope_change_impact(**params)
                elif scenario_type == 'resource_change':
                    report = await analyzer.analyze_resource_conflict(**params)
                else:
                    scenario_results.append({
                        'scenario_id': i,
                        'name': scenario.get('name', f'Scenario {i+1}'),
                        'error': f'Unknown scenario type: {scenario_type}'
                    })
                    continue
                
                scenario_results.append({
                    'scenario_id': i,
                    'name': scenario.get('name', f'Scenario {i+1}'),
                    'type': scenario_type,
                    'impact_level': report.impact_level.value,
                    'affected_tasks_count': len(report.affected_tasks),
                    'total_delay_days': report.total_delay_days,
                    'summary': report.summary,
                    'recommended_actions_count': len(report.recommended_actions)
                })
                
            except Exception as e:
                scenario_results.append({
                    'scenario_id': i,
                    'name': scenario.get('name', f'Scenario {i+1}'),
                    'error': str(e)
                })
        
        # Rank scenarios by impact (lower is better)
        severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        
        ranked = sorted(
            [s for s in scenario_results if 'error' not in s],
            key=lambda x: (
                severity_order.get(x['impact_level'], 4),
                x['total_delay_days'],
                x['affected_tasks_count']
            )
        )
        
        return {
            'comparison': {
                'scenarios_analyzed': len(request.scenarios),
                'successful': len([s for s in scenario_results if 'error' not in s]),
                'failed': len([s for s in scenario_results if 'error' in s])
            },
            'scenario_results': scenario_results,
            'recommendation': {
                'best_option': ranked[0] if ranked else None,
                'reasoning': f"'{ranked[0]['name']}' has lowest impact ({ranked[0]['impact_level']})" if ranked else None
            },
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to compare scenarios", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to compare: {str(e)}")
