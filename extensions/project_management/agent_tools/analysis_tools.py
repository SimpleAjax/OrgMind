"""
Analysis Tools for AI Agents

Tools for what-if analysis and recommendations.
"""

import logging
from typing import Dict, List, Optional, Any

from ..schedulers.impact_analyzer import ImpactAnalyzer
from ..schedulers.sprint_planner import SprintPlanner
from ..schedulers.skill_matcher import SkillMatcher

logger = logging.getLogger(__name__)


async def analyze_impact(
    db_adapter,
    neo4j_adapter,
    scenario_type: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze the impact of a hypothetical scenario.
    
    Args:
        db_adapter: Database adapter
        neo4j_adapter: Neo4j adapter
        scenario_type: Type of scenario ('leave', 'scope_change', 'resource_change')
        parameters: Scenario-specific parameters
        
    Returns:
        Impact analysis report
    """
    analyzer = ImpactAnalyzer(db_adapter, neo4j_adapter)
    
    if scenario_type == 'leave':
        # Parameters: person_id, start_date, end_date, leave_type
        report = await analyzer.analyze_leave_impact(**parameters)
    elif scenario_type == 'scope_change':
        # Parameters: project_id, added_tasks, removed_tasks
        report = await analyzer.analyze_scope_change_impact(**parameters)
    elif scenario_type == 'resource_change':
        # Parameters: person_id, date_range
        report = await analyzer.analyze_resource_conflict(**parameters)
    else:
        raise ValueError(f"Unknown scenario type: {scenario_type}")
    
    return {
        'scenario_type': scenario_type,
        'impact_level': report.impact_level.value,
        'summary': report.summary,
        'affected_projects': report.affected_projects,
        'affected_tasks': report.affected_tasks,
        'total_delay_days': report.total_delay_days,
        'recommended_actions': report.recommended_actions,
        'alternative_resources': report.alternative_resources,
        'parameters': report.parameters
    }


async def simulate_scope_change(
    db_adapter,
    neo4j_adapter,
    project_id: str,
    added_tasks: Optional[List[Dict[str, Any]]] = None,
    removed_task_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Simulate adding/removing tasks from a project without committing changes.
    
    Args:
        db_adapter: Database adapter
        neo4j_adapter: Neo4j adapter
        project_id: Project to simulate changes on
        added_tasks: Tasks to add (with title, estimated_hours, etc.)
        removed_task_ids: IDs of tasks to remove
        
    Returns:
        Simulation results
    """
    analyzer = ImpactAnalyzer(db_adapter, neo4j_adapter)
    
    # Get current state for baseline
    from ..schedulers.base import SchedulerBase
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        project = base.get_object_by_id(session, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get current project stats
        current_tasks = base.get_linked_objects(
            session, project_id, link_type_id='lt_project_has_task'
        )
        
        current_total_hours = sum(
            t['object'].data.get('estimated_hours', 0)
            for t in current_tasks
        )
        
        current_task_count = len(current_tasks)
    
    # Run impact analysis
    report = await analyzer.analyze_scope_change_impact(
        project_id=project_id,
        added_tasks=added_tasks or [],
        removed_tasks=removed_task_ids or []
    )
    
    # Calculate changes
    added_hours = sum(t.get('estimated_hours', 0) for t in (added_tasks or []))
    removed_hours = sum(
        t.get('estimated_hours', 0) 
        for t in report.affected_tasks 
        if any(rt == t.get('task_id') for rt in (removed_task_ids or []))
    )
    
    net_hours = added_hours - removed_hours
    new_total_hours = current_total_hours + net_hours
    
    return {
        'project_id': project_id,
        'project_name': project.data.get('name') if project else 'Unknown',
        'simulation': {
            'tasks_added': len(added_tasks or []),
            'tasks_removed': len(removed_task_ids or []),
            'hours_added': added_hours,
            'hours_removed': removed_hours,
            'net_hours': net_hours
        },
        'current_state': {
            'total_tasks': current_task_count,
            'total_hours': current_total_hours
        },
        'projected_state': {
            'total_tasks': current_task_count + len(added_tasks or []) - len(removed_task_ids or []),
            'total_hours': new_total_hours
        },
        'impact_assessment': {
            'impact_level': report.impact_level.value,
            'affected_projects_count': len(report.affected_projects),
            'timeline_delay_days': report.total_delay_days,
            'resource_conflicts': len(report.resource_conflicts)
        },
        'recommendations': [a['description'] for a in report.recommended_actions[:5]],
        'risk_factors': report.cost_impact if hasattr(report, 'cost_impact') else {},
        'can_commit': report.impact_level.value not in ['critical']
    }


async def get_sprint_recommendations(
    db_adapter,
    neo4j_adapter,
    sprint_id: str
) -> Dict[str, Any]:
    """
    Get AI recommendations for sprint planning.
    
    Args:
        db_adapter: Database adapter
        neo4j_adapter: Neo4j adapter
        sprint_id: Sprint to get recommendations for
        
    Returns:
        Sprint recommendations
    """
    planner = SprintPlanner(db_adapter, neo4j_adapter)
    
    # Generate recommendation
    recommendation = await planner.generate_sprint_recommendation(sprint_id)
    
    # Get current health
    health = await planner.check_sprint_health(sprint_id)
    
    # Format recommended tasks
    recommended_tasks = []
    for task in recommendation.recommended_tasks:
        recommended_tasks.append({
            'task_id': task.task_id,
            'title': task.task_title,
            'value_score': task.value_score,
            'effort_hours': task.effort_score,
            'risk_score': task.risk_score,
            'fit_score': task.fit_score,
            'recommended_assignee': task.recommended_assignee,
            'recommended_assignee_name': task.recommended_assignee_name,
            'skill_match': task.skill_match_score
        })
    
    # Format alternative tasks
    alternative_tasks = []
    for task in recommendation.alternative_tasks[:5]:  # Top 5 alternatives
        alternative_tasks.append({
            'task_id': task.task_id,
            'title': task.task_title,
            'value_score': task.value_score,
            'effort_hours': task.effort_score,
            'fit_score': task.fit_score,
            'excluded_reason': 'Capacity constraints' if task.risk_score > 50 else 'Lower priority'
        })
    
    # Format load distribution
    load_distribution = {}
    for person_id, alloc in recommendation.person_allocations.items():
        load_distribution[person_id] = {
            'name': alloc['name'],
            'allocated_hours': alloc['allocated_hours'],
            'task_count': alloc['task_count'],
            'tasks': [{'task_id': t['task_id'], 'title': t['title'], 'hours': t['hours']} 
                     for t in alloc['tasks']]
        }
    
    return {
        'sprint_id': sprint_id,
        'sprint_name': recommendation.sprint_name,
        'capacity': {
            'total_hours': recommendation.total_capacity_hours,
            'recommended_commitment': recommendation.recommended_commitment_hours,
            'utilization_target': recommendation.utilization_target,
            'projected_utilization': recommendation.recommended_commitment_hours / recommendation.total_capacity_hours if recommendation.total_capacity_hours > 0 else 0
        },
        'recommended_tasks': recommended_tasks,
        'total_value_score': recommendation.total_value_score,
        'task_count': len(recommended_tasks),
        'load_distribution': load_distribution,
        'risk_assessment': {
            'overall_risk_score': recommendation.overall_risk_score,
            'risk_factors': recommendation.risk_factors,
            'risk_level': 'high' if recommendation.overall_risk_score > 60 else 'medium' if recommendation.overall_risk_score > 40 else 'low'
        },
        'alternative_tasks': alternative_tasks,
        'reasoning': recommendation.recommendation_reasoning,
        'current_health': {
            'status': health.status.value,
            'score': health.health_score,
            'completion': health.completion_percentage
        } if health else None
    }


async def find_skill_matches(
    db_adapter,
    task_id: str,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Find the best people for a task based on skills.
    
    Args:
        db_adapter: Database adapter
        task_id: Task to find matches for
        limit: Maximum number of matches
        
    Returns:
        Skill match results
    """
    matcher = SkillMatcher(db_adapter)
    
    # Get matches
    matches = await matcher.find_best_matches(task_id, limit=limit)
    
    # Get task info
    from ..schedulers.base import SchedulerBase
    base = SchedulerBase(db_adapter)
    
    with base.get_session() as session:
        task = base.get_object_by_id(session, task_id)
        
        # Get skill requirements
        skill_reqs = matcher._get_task_skill_requirements(session, task_id)
        
        requirements = []
        for req in skill_reqs:
            requirements.append({
                'skill_id': req['skill_id'],
                'skill_name': req['skill_name'],
                'required_level': req['min_proficiency'],
                'is_mandatory': req['is_mandatory']
            })
    
    # Format matches
    formatted_matches = []
    for match in matches:
        formatted_matches.append({
            'person_id': match.person_id,
            'person_name': match.person_name,
            'match_score': match.match_score,
            'is_full_match': match.is_full_match,
            'availability_percent': match.availability_percent,
            'matching_skills': [
                {
                    'skill_name': s['skill_name'],
                    'required_level': s['required_level'],
                    'person_level': s['actual']
                }
                for s in match.matching_skills
            ],
            'missing_skills': [
                {
                    'skill_name': s['skill_name'],
                    'required_level': s['required_level']
                }
                for s in match.missing_skills
            ],
            'development_opportunities': [
                {
                    'skill_name': d['skill_name'],
                    'current_level': d['current_level'],
                    'target_level': d['target_level']
                }
                for d in match.development_opportunities
            ],
            'recommendation': match.recommendation
        })
    
    return {
        'task_id': task_id,
        'task_title': task.data.get('title') if task else 'Unknown',
        'requirements': requirements,
        'matches': formatted_matches,
        'best_match': formatted_matches[0] if formatted_matches else None,
        'has_perfect_match': any(m['match_score'] >= 90 for m in formatted_matches),
        'has_full_match': any(m['is_full_match'] for m in formatted_matches)
    }
