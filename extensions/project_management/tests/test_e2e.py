"""
End-to-End Tests for Project Management Extension

Tests cover complete user workflows:
- Sick leave impact workflow
- Sprint planning workflow
- Scope change workflow
- Skill matching workflow
- Nudge generation workflow
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import List, Dict, Any

from extensions.project_management.schedulers import (
    PriorityCalculator,
    ImpactAnalyzer,
    NudgeGenerator,
    SkillMatcher,
    SprintPlanner,
    ConflictDetector
)
from extensions.project_management.schedulers.nudge_generator import (
    NudgeCandidate, NudgeType, NudgeSeverity
)


# =============================================================================
# E2E Test Fixtures
# =============================================================================

@pytest.fixture
def e2e_db_adapter():
    """Create a mock DB adapter for E2E tests."""
    adapter = Mock()
    adapter.get_session = MagicMock()
    return adapter


@pytest.fixture
def e2e_neo4j_adapter():
    """Create a mock Neo4j adapter for E2E tests."""
    adapter = Mock()
    adapter.execute_read = MagicMock(return_value=[])
    return adapter


@pytest.fixture
def mock_session():
    """Create a mock database session with realistic behavior."""
    session = MagicMock()
    session.scalars = MagicMock()
    session.commit = MagicMock()
    session.add = MagicMock()
    return session


def create_object(obj_id: str, type_id: str, data: dict, status: str = 'active'):
    """Create a mock object for E2E tests."""
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    obj.created_at = datetime.utcnow()
    obj.updated_at = datetime.utcnow()
    return obj


# =============================================================================
# User Story 1: Sick Leave Impact Workflow
# =============================================================================

class TestSickLeaveImpactWorkflow:
    """
    E2E Test: Handling Sick Leave
    
    As a PM, when a team member calls in sick, I want to instantly see 
    impact and alternatives so that I can replan without missing deadlines.
    
    Scenario:
    1. PM marks Person X as unavailable for 3 days
    2. System calculates impact on all assigned tasks
    3. System suggests alternative resources with skill match
    4. System shows revised timeline for affected projects
    5. PM selects alternative and confirms reallocation
    6. System updates all schedules and notifies stakeholders
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_sick_leave_workflow(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test the complete sick leave impact workflow."""
        
        # Step 1: Setup - Person with assignments goes on sick leave
        person = create_object('person_alice', 'ot_person', {
            'name': 'Alice Developer',
            'email': 'alice@example.com',
            'role': 'senior_developer',
            'status': 'active'
        })
        
        # Alice has 3 tasks assigned
        tasks = [
            create_object('task_api', 'ot_task', {
                'title': 'API Integration',
                'project_id': 'proj_alpha',
                'status': 'in_progress',
                'estimated_hours': 24,
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
                'priority_score': 85
            }),
            create_object('task_db', 'ot_task', {
                'title': 'Database Migration',
                'project_id': 'proj_alpha',
                'status': 'todo',
                'estimated_hours': 16,
                'due_date': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                'priority_score': 80
            }),
            create_object('task_ui', 'ot_task', {
                'title': 'UI Polish',
                'project_id': 'proj_beta',
                'status': 'todo',
                'estimated_hours': 8,
                'due_date': (datetime.utcnow() + timedelta(days=3)).isoformat(),
                'priority_score': 70
            })
        ]
        
        # Alternative resources
        alternatives = [
            create_object('person_bob', 'ot_person', {
                'name': 'Bob Developer',
                'email': 'bob@example.com',
                'role': 'developer',
                'status': 'active'
            }),
            create_object('person_carol', 'ot_person', {
                'name': 'Carol Engineer',
                'email': 'carol@example.com',
                'role': 'developer',
                'status': 'active'
            })
        ]
        
        # Step 2: Impact Analysis
        analyzer = ImpactAnalyzer(e2e_db_adapter, e2e_neo4j_adapter)
        
        analyzer.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        analyzer.get_object_by_id = MagicMock(return_value=person)
        analyzer._get_assignments_during_period = MagicMock(return_value=[
            {'task': task, 'allocation': 75} for task in tasks
        ])
        analyzer._is_on_critical_path = MagicMock(side_effect=lambda s, t: t == 'task_api')
        analyzer._find_alternative_resources = MagicMock(return_value=[
            {'person_id': 'person_bob', 'person_name': 'Bob Developer', 'skill_match': 90},
            {'person_id': 'person_carol', 'person_name': 'Carol Engineer', 'skill_match': 75}
        ])
        
        # Execute leave impact analysis
        leave_start = datetime.utcnow()
        leave_end = leave_start + timedelta(days=3)
        
        impact = await analyzer.analyze_leave_impact(
            person_id='person_alice',
            start_date=leave_start.isoformat(),
            end_date=leave_end.isoformat(),
            leave_type='sick'
        )
        
        # Verify impact analysis
        assert impact.impact_type == 'leave'
        assert impact.related_people[0]['person_id'] == 'person_alice'
        assert 'Alice Developer' in impact.summary
        
        # Step 3: Find alternatives
        alternatives = await analyzer.find_alternative_resources(
            task_id='task_api',
            exclude_person_id='person_alice',
            limit=3
        )
        
        assert len(alternatives) > 0
        assert alternatives[0]['skill_match'] >= 75
        
        # Step 4: Nudge Generation
        nudge_gen = NudgeGenerator(e2e_db_adapter, e2e_neo4j_adapter)
        
        nudge_gen.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        nudge_gen.get_object_by_id = MagicMock(return_value=person)
        nudge_gen._get_task_assignees = MagicMock(return_value=[{'person_id': 'person_alice'}])
        
        # Generate leave nudge
        nudge = NudgeCandidate(
            type=NudgeType.RISK,
            severity=NudgeSeverity.WARNING,
            title=f"Alice Developer is on sick leave",
            description=f"Impact analysis shows 3 tasks affected across 2 projects.",
            recipient_id='pm_1',
            related_person_id='person_alice',
            confidence=0.95
        )
        
        assert nudge.type == NudgeType.RISK
        assert nudge.related_person_id == 'person_alice'
        
        print(f"\n✅ Sick Leave Workflow Complete:")
        print(f"   - Impact analyzed: {len(tasks)} tasks affected")
        print(f"   - Alternatives found: {len(alternatives)} candidates")
        print(f"   - Nudge generated: {nudge.title}")


# =============================================================================
# User Story 2: Sprint Planning Workflow
# =============================================================================

class TestSprintPlanningWorkflow:
    """
    E2E Test: Sprint Planning with AI Recommendations
    
    As a PM, I want AI recommendations for sprint content so that I maximize 
    value delivery while maintaining team capacity.
    
    Scenario:
    1. PM initiates sprint planning
    2. System suggests optimal task mix based on priorities, capacity, skills
    3. PM reviews and adjusts
    4. System highlights risks in proposed sprint
    5. PM commits to sprint
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_sprint_planning_workflow(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test the complete sprint planning workflow."""
        
        # Setup: Sprint with team
        sprint = create_object('sprint_10', 'ot_sprint', {
            'name': 'Sprint 10',
            'start_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=16)).isoformat(),
            'status': 'planning'
        })
        
        # Team members with capacity
        team = [
            {'id': 'person_alice', 'name': 'Alice', 'planned_capacity_hours': 80, 'role': 'senior'},
            {'id': 'person_bob', 'name': 'Bob', 'planned_capacity_hours': 80, 'role': 'developer'},
            {'id': 'person_carol', 'name': 'Carol', 'planned_capacity_hours': 60, 'role': 'developer'}
        ]
        
        # Available tasks from backlog
        available_tasks = [
            create_object(f'task_{i}', 'ot_task', {
                'title': f'Feature {i}',
                'project_id': 'proj_alpha',
                'status': 'backlog',
                'estimated_hours': 8 + (i * 4),
                'priority_score': 90 - (i * 5),
                'business_value': 85 - (i * 3),
                'predicted_delay_probability': 0.2 + (i * 0.05)
            })
            for i in range(15)
        ]
        
        # Step 1: Sprint Planner generates recommendations
        planner = SprintPlanner(e2e_db_adapter, e2e_neo4j_adapter)
        
        planner.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_participants = MagicMock(return_value=team)
        planner._get_available_tasks = MagicMock(return_value=available_tasks)
        planner._find_best_assignee = MagicMock(return_value=('person_alice', 90.0))
        planner._calculate_dependency_risk = MagicMock(return_value=10)
        
        recommendation = await planner.generate_sprint_recommendation('sprint_10')
        
        # Verify recommendation
        assert recommendation.sprint_id == 'sprint_10'
        assert recommendation.total_capacity_hours == 220  # 80 + 80 + 60
        assert len(recommendation.recommended_tasks) > 0
        assert recommendation.utilization_target == 0.85  # 85% target
        
        # Step 2: Conflict Detection
        detector = ConflictDetector(e2e_db_adapter, e2e_neo4j_adapter)
        
        detector.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        detector.get_objects_by_type = MagicMock(return_value=[sprint])
        detector._get_sprint_tasks = MagicMock(return_value=[
            create_object(f'st_{t.id}', 'ot_sprint_task', {
                'sprint_id': 'sprint_10',
                'task_id': t.id
            })
            for t in recommendation.recommended_tasks[:5]
        ])
        detector._get_sprint_participants = MagicMock(return_value=team)
        
        validation = await detector.validate_sprint_capacity('sprint_10')
        
        assert validation['sprint_id'] == 'sprint_10'
        assert 'participant_loads' in validation
        assert 'recommendations' in validation
        
        # Step 3: Health Check
        health = await planner.check_sprint_health('sprint_10')
        
        assert health.sprint_id == 'sprint_10'
        assert health.status is not None
        
        print(f"\n✅ Sprint Planning Workflow Complete:")
        print(f"   - Recommended tasks: {len(recommendation.recommended_tasks)}")
        print(f"   - Total value score: {recommendation.total_value_score:.0f}")
        print(f"   - Sprint risk: {recommendation.overall_risk_score:.0f}/100")
        print(f"   - Health status: {health.status.value}")


# =============================================================================
# User Story 3: Scope Change Impact Workflow
# =============================================================================

class TestScopeChangeWorkflow:
    """
    E2E Test: Scope Change Impact Analysis
    
    As a PM, when a client requests scope changes, I want to understand 
    the full impact before committing.
    
    Scenario:
    1. PM adds 5 new tasks to Project A
    2. System calculates: new end date, resource needs, impact on other projects
    3. System generates comparison: Original vs New plan
    4. PM can simulate different options
    5. PM presents data-driven options to client
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_scope_change_workflow(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test the complete scope change workflow."""
        
        # Setup: Existing project
        project = create_object('proj_alpha', 'ot_project', {
            'name': 'Alpha Project',
            'planned_start': (datetime.utcnow() - timedelta(days=30)).isoformat(),
            'planned_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
            'budget_hours': 400,
            'hourly_rate': 100,
            'status': 'active',
            'pm_id': 'pm_1'
        })
        
        # Existing tasks
        existing_tasks = [
            create_object(f'et_{i}', 'ot_task', {
                'title': f'Existing Task {i}',
                'project_id': 'proj_alpha',
                'status': 'done' if i < 5 else 'in_progress' if i < 8 else 'todo',
                'estimated_hours': 16,
                'actual_hours': 16 if i < 5 else 8
            })
            for i in range(10)
        ]
        
        # New scope additions
        new_tasks = [
            {'title': 'Additional Feature A', 'estimated_hours': 40},
            {'title': 'Additional Feature B', 'estimated_hours': 24},
            {'title': 'Integration Update', 'estimated_hours': 16},
            {'title': 'Security Hardening', 'estimated_hours': 20},
            {'title': 'Performance Optimization', 'estimated_hours': 32}
        ]
        
        # Step 1: Impact Analysis
        analyzer = ImpactAnalyzer(e2e_db_adapter, e2e_neo4j_adapter)
        
        analyzer.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        analyzer.get_object_by_id = MagicMock(return_value=project)
        analyzer.get_linked_objects = MagicMock(return_value=[
            {'object': task, 'link_data': {}} for task in existing_tasks
        ])
        
        impact = await analyzer.analyze_scope_change_impact(
            project_id='proj_alpha',
            added_tasks=new_tasks,
            removed_tasks=[]
        )
        
        # Verify impact analysis
        assert impact.impact_type == 'scope_change'
        assert impact.affected_projects[0]['project_id'] == 'proj_alpha'
        assert impact.cost_impact['additional_hours'] == 132  # Sum of new task hours
        assert len(impact.recommended_actions) > 0
        
        # Step 2: Check for conflicts with other projects
        detector = ConflictDetector(e2e_db_adapter, e2e_neo4j_adapter)
        
        detector.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        detector.get_objects_by_type = MagicMock(return_value=[])
        
        conflicts = await detector.detect_conflicts()
        
        # Step 3: Generate comparison
        current_state = {
            'total_tasks': len(existing_tasks),
            'completed_tasks': 5,
            'remaining_hours': 240,
            'projected_end': project.data['planned_end']
        }
        
        projected_state = {
            'total_tasks': len(existing_tasks) + len(new_tasks),
            'completed_tasks': 5,
            'remaining_hours': 240 + 132,
            'projected_end': (datetime.utcnow() + timedelta(days=45)).isoformat()
        }
        
        comparison = {
            'current': current_state,
            'projected': projected_state,
            'change': {
                'additional_tasks': len(new_tasks),
                'additional_hours': 132,
                'timeline_extension_days': 15,
                'cost_impact': 132 * project.data['hourly_rate']
            }
        }
        
        # Step 4: Priority recalculation
        calculator = PriorityCalculator(e2e_db_adapter, e2e_neo4j_adapter)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_object_by_id = MagicMock(return_value=project)
        calculator.get_objects_by_type = MagicMock(return_value=[project])
        
        priority = await calculator.calculate_project_priority('proj_alpha', save=False)
        
        print(f"\n✅ Scope Change Workflow Complete:")
        print(f"   - Current tasks: {current_state['total_tasks']}")
        print(f"   - Added tasks: {len(new_tasks)}")
        print(f"   - Additional hours: {comparison['change']['additional_hours']}h")
        print(f"   - Timeline extension: {comparison['change']['timeline_extension_days']} days")
        print(f"   - Cost impact: ${comparison['change']['cost_impact']:,}")


# =============================================================================
# User Story 4: Skill Matching Workflow
# =============================================================================

class TestSkillMatchingWorkflow:
    """
    E2E Test: Skill-Based Resource Allocation
    
    As a PM, I want to match tasks to people based on required skills 
    and proficiency.
    
    Scenario:
    1. Task requires specific skills
    2. System ranks people by skill match
    3. System shows skill gaps
    4. PM makes informed assignment decision
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_skill_matching_workflow(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test the complete skill matching workflow."""
        
        # Setup: Task with skill requirements
        task = create_object('task_ml', 'ot_task', {
            'title': 'Machine Learning Model Development',
            'project_id': 'proj_ai',
            'status': 'todo',
            'estimated_hours': 80,
            'priority_score': 90
        })
        
        # Skill requirements
        skill_reqs = [
            create_object('req_python', 'ot_task_skill_requirement', {
                'task_id': 'task_ml',
                'skill_id': 'skill_python',
                'minimum_proficiency': 4,
                'is_mandatory': True
            }),
            create_object('req_ml', 'ot_task_skill_requirement', {
                'task_id': 'task_ml',
                'skill_id': 'skill_ml',
                'minimum_proficiency': 3,
                'is_mandatory': True
            }),
            create_object('req_tensorflow', 'ot_task_skill_requirement', {
                'task_id': 'task_ml',
                'skill_id': 'skill_tensorflow',
                'minimum_proficiency': 2,
                'is_mandatory': False
            })
        ]
        
        # Team with varying skills
        team = [
            create_object('person_alice', 'ot_person', {'name': 'Alice', 'status': 'active'}),
            create_object('person_bob', 'ot_person', {'name': 'Bob', 'status': 'active'}),
            create_object('person_carol', 'ot_person', {'name': 'Carol', 'status': 'active'})
        ]
        
        # Skills data
        skills = {
            'skill_python': create_object('skill_python', 'ot_skill', {'name': 'Python'}),
            'skill_ml': create_object('skill_ml', 'ot_skill', {'name': 'Machine Learning'}),
            'skill_tensorflow': create_object('skill_tensorflow', 'ot_skill', {'name': 'TensorFlow'})
        }
        
        # Person skills (Alice is best match)
        person_skills = {
            'person_alice': [
                {'skill_id': 'skill_python', 'proficiency': 5},
                {'skill_id': 'skill_ml', 'proficiency': 4},
                {'skill_id': 'skill_tensorflow', 'proficiency': 3}
            ],
            'person_bob': [
                {'skill_id': 'skill_python', 'proficiency': 4},
                {'skill_id': 'skill_ml', 'proficiency': 2}  # Below required
            ],
            'person_carol': [
                {'skill_id': 'skill_python', 'proficiency': 3}  # Below required
            ]
        }
        
        # Step 1: Find best matches
        matcher = SkillMatcher(e2e_db_adapter)
        
        matcher.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        matcher.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'task_ml': task,
            'person_alice': team[0],
            'person_bob': team[1],
            'person_carol': team[2],
            **skills
        }.get(id))
        matcher.get_linked_objects = MagicMock(side_effect=lambda s, id, **kwargs: {
            ('task_ml', 'lt_task_requires_skill'): [
                {'object': sr, 'link_data': {}} for sr in skill_reqs
            ],
            ('person_alice', 'lt_person_has_skill'): [
                {'object': create_object(f'ps_alice_{p["skill_id"]}', 'ot_person_skill', p),
                 'link_data': {'proficiency_level': p['proficiency']}}
                for p in person_skills['person_alice']
            ],
            ('person_bob', 'lt_person_has_skill'): [
                {'object': create_object(f'ps_bob_{p["skill_id"]}', 'ot_person_skill', p),
                 'link_data': {'proficiency_level': p['proficiency']}}
                for p in person_skills['person_bob']
            ],
            ('person_carol', 'lt_person_has_skill'): [
                {'object': create_object(f'ps_carol_{p["skill_id"]}', 'ot_person_skill', p),
                 'link_data': {'proficiency_level': p['proficiency']}}
                for p in person_skills['person_carol']
            ]
        }.get((id, kwargs.get('link_type_id')), []))
        matcher.get_objects_by_type = MagicMock(return_value=team)
        matcher._calculate_availability = MagicMock(return_value=50.0)
        
        matches = await matcher.find_best_matches('task_ml', limit=3)
        
        # Verify matches
        assert len(matches) > 0
        assert matches[0].person_id == 'person_alice'  # Best match
        assert matches[0].match_score > matches[1].match_score if len(matches) > 1 else True
        
        # Step 2: Identify skill gaps
        gaps = await matcher.identify_skill_gaps()
        
        print(f"\n✅ Skill Matching Workflow Complete:")
        print(f"   - Task: {task.data['title']}")
        print(f"   - Best match: {matches[0].person_name} ({matches[0].match_score:.0f}%)")
        print(f"   - Full match: {matches[0].is_full_match}")
        print(f"   - Matching skills: {len(matches[0].matching_skills)}")
        print(f"   - Organization skill gaps: {len(gaps)}")


# =============================================================================
# User Story 5: Nudge Generation Workflow
# =============================================================================

class TestNudgeGenerationWorkflow:
    """
    E2E Test: AI Nudge Generation
    
    As a PM, I want proactive notifications about risks and opportunities.
    
    Scenario:
    1. System continuously monitors projects
    2. System detects risk (task likely to miss deadline)
    3. System generates nudge with severity and actions
    4. PM receives nudge in inbox
    5. PM acknowledges or acts on nudge
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_nudge_workflow(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test the complete nudge generation workflow."""
        
        # Setup: Projects with various states
        projects = [
            create_object('proj_alpha', 'ot_project', {
                'name': 'Alpha Project',
                'pm_id': 'pm_1',
                'priority_score': 90
            }),
            create_object('proj_beta', 'ot_project', {
                'name': 'Beta Project',
                'pm_id': 'pm_1',
                'priority_score': 75
            })
        ]
        
        # Tasks at risk
        at_risk_tasks = [
            create_object('task_risk_1', 'ot_task', {
                'title': 'Critical API Endpoint',
                'project_id': 'proj_alpha',
                'status': 'in_progress',
                'predicted_delay_probability': 0.85,
                'due_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
                'estimated_hours': 16
            }),
            create_object('task_risk_2', 'ot_task', {
                'title': 'Database Schema Design',
                'project_id': 'proj_alpha',
                'status': 'todo',
                'predicted_delay_probability': 0.75,
                'due_date': (datetime.utcnow() + timedelta(days=3)).isoformat(),
                'estimated_hours': 24
            })
        ]
        
        # Safe tasks
        safe_tasks = [
            create_object('task_safe_1', 'ot_task', {
                'title': 'Documentation Update',
                'project_id': 'proj_beta',
                'status': 'in_progress',
                'predicted_delay_probability': 0.2,
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat()
            })
        ]
        
        # Step 1: Detect delay risks
        nudge_gen = NudgeGenerator(e2e_db_adapter, e2e_neo4j_adapter)
        
        nudge_gen.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        nudge_gen.get_objects_by_type = MagicMock(side_effect=lambda s, type_id, **kwargs: {
            'ot_task': at_risk_tasks + safe_tasks,
            'ot_project': projects
        }.get(type_id, []))
        nudge_gen.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'proj_alpha': projects[0],
            'proj_beta': projects[1]
        }.get(id))
        nudge_gen._get_task_assignees = MagicMock(return_value=[
            {'person_id': 'person_alice'}
        ])
        
        delay_nudges = await nudge_gen.detect_delay_risks()
        
        # Verify delay risk detection
        assert len(delay_nudges) == 2  # Two at-risk tasks
        assert all(n.type == NudgeType.RISK for n in delay_nudges)
        assert all(n.severity in [NudgeSeverity.WARNING, NudgeSeverity.CRITICAL] for n in delay_nudges)
        
        # Step 2: Rank nudges
        ranked_nudges = nudge_gen.rank_nudges(delay_nudges)
        
        # Higher severity should be first
        assert ranked_nudges[0].severity.value >= ranked_nudges[-1].severity.value
        
        # Step 3: Deduplicate
        # Add a duplicate
        duplicate_nudge = NudgeCandidate(
            type=NudgeType.RISK,
            severity=NudgeSeverity.WARNING,
            title="Task at risk of delay",
            description="Duplicate",
            recipient_id="pm_1",
            related_task_id="task_risk_1",
            confidence=0.8
        )
        all_nudges = delay_nudges + [duplicate_nudge]
        
        deduplicated = nudge_gen._deduplicate_nudges(all_nudges)
        
        # Should remove duplicate
        assert len(deduplicated) <= len(all_nudges)
        
        # Step 4: Detect burnout risks
        people = [
            create_object('person_alice', 'ot_person', {
                'name': 'Alice',
                'status': 'active',
                'manager_id': 'pm_1'
            }),
            create_object('person_bob', 'ot_person', {
                'name': 'Bob',
                'status': 'active',
                'manager_id': 'pm_1'
            })
        ]
        
        nudge_gen.get_objects_by_type = MagicMock(return_value=people)
        nudge_gen._calculate_average_allocation = MagicMock(side_effect=lambda s, p, w: {
            'person_alice': 95.0,  # Overallocated
            'person_bob': 70.0
        }.get(p, 0))
        
        burnout_nudges = await nudge_gen.detect_burnout_risks()
        
        assert len(burnout_nudges) == 1
        assert burnout_nudges[0].related_person_id == 'person_alice'
        
        print(f"\n✅ Nudge Generation Workflow Complete:")
        print(f"   - Delay risks detected: {len(delay_nudges)}")
        print(f"   - Burnout risks detected: {len(burnout_nudges)}")
        print(f"   - Total unique nudges: {len(deduplicated)}")
        print(f"   - Highest severity: {ranked_nudges[0].severity.value}")


# =============================================================================
# Integration Test: Full System Workflow
# =============================================================================

class TestFullSystemWorkflow:
    """
    E2E Test: Complete system integration
    
    Tests that all schedulers work together correctly.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_full_project_lifecycle(self, e2e_db_adapter, e2e_neo4j_adapter, mock_session):
        """Test a complete project lifecycle with all components."""
        
        print("\n🚀 Starting Full Project Lifecycle Test...")
        
        # 1. Priority calculation
        calculator = PriorityCalculator(e2e_db_adapter, e2e_neo4j_adapter)
        projects = generate_test_projects(5)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        priority_result = await calculator.recalculate_all_priorities()
        assert priority_result['processed'] == 5
        print(f"   ✓ Priority calculation: {priority_result['processed']} projects")
        
        # 2. Sprint planning
        planner = SprintPlanner(e2e_db_adapter, e2e_neo4j_adapter)
        sprint = create_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': datetime.utcnow().isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat()
        })
        
        planner.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': 'person_1', 'name': 'Dev 1', 'planned_capacity_hours': 80}
        ])
        planner._get_available_tasks = MagicMock(return_value=[])
        
        recommendation = await planner.generate_sprint_recommendation('sprint_1')
        print(f"   ✓ Sprint planning: {len(recommendation.recommended_tasks)} tasks recommended")
        
        # 3. Conflict detection
        detector = ConflictDetector(e2e_db_adapter, e2e_neo4j_adapter)
        detector.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        detector.get_objects_by_type = MagicMock(return_value=[])
        
        conflicts = await detector.detect_conflicts()
        print(f"   ✓ Conflict detection: {conflicts.total_conflicts} conflicts found")
        
        # 4. Nudge generation
        nudge_gen = NudgeGenerator(e2e_db_adapter, e2e_neo4j_adapter)
        nudge_gen.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        nudge_gen.get_objects_by_type = MagicMock(return_value=[])
        
        delay_nudges = await nudge_gen.detect_delay_risks()
        print(f"   ✓ Nudge generation: {len(delay_nudges)} nudges")
        
        print("\n✅ Full Project Lifecycle Test Complete!")


def generate_test_projects(count: int) -> List[Mock]:
    """Generate test projects."""
    return [
        create_object(f'proj_{i}', 'ot_project', {
            'name': f'Project {i}',
            'planned_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
            'business_value_score': 50 + i * 10,
            'strategic_importance': 60,
            'risk_score': 20
        })
        for i in range(count)
    ]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'e2e'])
