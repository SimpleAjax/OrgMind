"""
Tests for Phase 3 Advanced Features

Tests cover:
- SprintPlanner
- VelocityCalculator
- ConflictDetector
- Agent Tools
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from extensions.project_management.schedulers import (
    SprintPlanner,
    VelocityCalculator,
    ConflictDetector
)
from extensions.project_management.schedulers.sprint_planner import (
    TaskScore, SprintRecommendation, SprintHealth, SprintHealthStatus
)
from extensions.project_management.schedulers.velocity_calculator import (
    VelocityMetrics, TaskVelocityRecord
)
from extensions.project_management.schedulers.conflict_detector import (
    Conflict, ConflictType, ConflictSeverity
)
from extensions.project_management.agent_tools import (
    query_projects,
    query_tasks,
    get_project_health,
    get_person_utilization,
    analyze_impact,
    find_skill_matches,
    create_nudge,
    reassign_task
)


# =============================================================================
# Sprint Planner Tests
# =============================================================================

class TestSprintPlanner:
    """Tests for SprintPlanner."""
    
    @pytest.fixture
    def planner(self, mock_db_adapter, mock_neo4j_adapter):
        return SprintPlanner(mock_db_adapter, mock_neo4j_adapter)
    
    @pytest.mark.asyncio
    async def test_score_task_for_sprint(self, planner, mock_session):
        """Test task scoring for sprint context."""
        task = create_mock_object('task_1', 'ot_task', {
            'title': 'Important Feature',
            'project_id': 'proj_1',
            'estimated_hours': 16,
            'priority_score': 80,
            'business_value': 90,
            'predicted_delay_probability': 0.2
        })
        
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': datetime.utcnow().isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat()
        })
        
        participants = [{'id': 'person_1', 'name': 'Developer', 'planned_capacity_hours': 80}]
        
        planner.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        planner.get_object_by_id = MagicMock(return_value=None)
        planner.get_linked_objects = MagicMock(return_value=[])
        planner._find_best_assignee = MagicMock(return_value=('person_1', 85.0))
        planner._calculate_dependency_risk = MagicMock(return_value=10)
        
        score = await planner.score_task_for_sprint(mock_session, task, sprint, participants)
        
        assert isinstance(score, TaskScore)
        assert score.task_id == 'task_1'
        assert score.value_score > 50  # High value task
        assert score.effort_score == 16  # Hours
        assert score.fit_score > 0
        assert score.recommended_assignee == 'person_1'
    
    @pytest.mark.asyncio
    async def test_generate_sprint_recommendation(self, planner, mock_session):
        """Test sprint recommendation generation."""
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': datetime.utcnow().isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat()
        })
        
        planner.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': 'person_1', 'name': 'Dev 1', 'planned_capacity_hours': 80},
            {'id': 'person_2', 'name': 'Dev 2', 'planned_capacity_hours': 80}
        ])
        planner._get_available_tasks = MagicMock(return_value=[])
        
        recommendation = await planner.generate_sprint_recommendation('sprint_1')
        
        assert isinstance(recommendation, SprintRecommendation)
        assert recommendation.sprint_id == 'sprint_1'
        assert recommendation.total_capacity_hours == 160  # 80 + 80
        assert recommendation.utilization_target == 0.85
    
    @pytest.mark.asyncio
    async def test_check_sprint_health(self, planner, mock_session):
        """Test sprint health check."""
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=7)).isoformat()
        })
        
        planner.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_tasks = MagicMock(return_value=[
            create_mock_object('task_1', 'ot_task', {'status': 'done', 'estimated_hours': 8, 'actual_hours': 8}),
            create_mock_object('task_2', 'ot_task', {'status': 'in_progress', 'estimated_hours': 8}),
            create_mock_object('task_3', 'ot_task', {'status': 'blocked', 'estimated_hours': 8}),
        ])
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': 'person_1', 'name': 'Dev 1', 'planned_capacity_hours': 80}
        ])
        planner._calculate_team_utilization = MagicMock(return_value={'person_1': 75})
        
        health = await planner.check_sprint_health('sprint_1')
        
        assert isinstance(health, SprintHealth)
        assert health.sprint_id == 'sprint_1'
        assert health.total_tasks == 3
        assert health.completed_tasks == 1
        assert health.blocked_tasks_count == 1
        assert health.completion_percentage == pytest.approx(33.33, 0.1)


# =============================================================================
# Velocity Calculator Tests
# =============================================================================

class TestVelocityCalculator:
    """Tests for VelocityCalculator."""
    
    @pytest.fixture
    def calculator(self, mock_db_adapter):
        return VelocityCalculator(mock_db_adapter)
    
    @pytest.mark.asyncio
    async def test_calculate_velocity_metrics(self, calculator, mock_session):
        """Test velocity metrics calculation."""
        person = create_mock_object('person_1', 'ot_person', {'name': 'Developer'})
        
        tasks = [
            TaskVelocityRecord(
                task_id='task_1',
                task_title='Task 1',
                project_id='proj_1',
                project_type='time_material',
                estimated_hours=8,
                actual_hours=8,
                variance_ratio=1.0,
                started_at=datetime.utcnow() - timedelta(days=2),
                completed_at=datetime.utcnow(),
                completion_days=2,
                assignee_id='person_1'
            ),
            TaskVelocityRecord(
                task_id='task_2',
                task_title='Task 2',
                project_id='proj_1',
                project_type='time_material',
                estimated_hours=8,
                actual_hours=6,  # Faster than estimated
                variance_ratio=0.75,
                started_at=datetime.utcnow() - timedelta(days=1),
                completed_at=datetime.utcnow(),
                completion_days=1,
                assignee_id='person_1'
            )
        ]
        
        metrics = calculator._calculate_velocity_metrics(person, 'time_material', tasks)
        
        assert isinstance(metrics, VelocityMetrics)
        assert metrics.person_id == 'person_1'
        assert metrics.project_type == 'time_material'
        assert metrics.tasks_completed == 2
        assert metrics.velocity_factor > 1.0  # Faster than average
        assert metrics.estimation_accuracy > 0
    
    @pytest.mark.asyncio
    async def test_update_productivity_profiles(self, calculator, mock_session):
        """Test batch profile updates."""
        person = create_mock_object('person_1', 'ot_person', {'name': 'Developer', 'status': 'active'})
        
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        calculator.get_objects_by_type = MagicMock(return_value=[person])
        calculator._get_completed_tasks = MagicMock(return_value=[
            TaskVelocityRecord('task_1', 'T1', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1'),
            TaskVelocityRecord('task_2', 'T2', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1'),
            TaskVelocityRecord('task_3', 'T3', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1'),
        ])
        calculator._group_tasks_by_project_type = MagicMock(return_value={
            'time_material': [
                TaskVelocityRecord('task_1', 'T1', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1'),
                TaskVelocityRecord('task_2', 'T2', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1'),
            ]
        })
        calculator._update_productivity_profile = MagicMock()
        
        result = await calculator.update_productivity_profiles(min_sample_size=2)
        
        assert result['updated'] == 1
        assert result['skipped'] == 0
    
    @pytest.mark.asyncio
    async def test_remove_outliers(self, calculator):
        """Test outlier removal in velocity calculation."""
        tasks = [
            TaskVelocityRecord(f'task_{i}', f'T{i}', 'proj_1', 'time_material', 8, 8, 1.0, None, datetime.utcnow(), 1, 'person_1')
            for i in range(8)
        ]
        # Add outliers
        tasks.append(TaskVelocityRecord('outlier_1', 'Outlier', 'proj_1', 'time_material', 8, 100, 12.5, None, datetime.utcnow(), 10, 'person_1'))
        tasks.append(TaskVelocityRecord('outlier_2', 'Outlier', 'proj_1', 'time_material', 8, 0.5, 0.06, None, datetime.utcnow(), 0, 'person_1'))
        
        values = [t.variance_ratio for t in tasks]
        filtered = calculator._remove_outliers(tasks, values)
        
        # Should filter out extreme outliers
        assert len(filtered) <= len(tasks)


# =============================================================================
# Conflict Detector Tests
# =============================================================================

class TestConflictDetector:
    """Tests for ConflictDetector."""
    
    @pytest.fixture
    def detector(self, mock_db_adapter, mock_neo4j_adapter):
        return ConflictDetector(mock_db_adapter, mock_neo4j_adapter)
    
    @pytest.mark.asyncio
    async def test_detect_overallocations(self, detector, mock_session):
        """Test overallocation detection."""
        person = create_mock_object('person_1', 'ot_person', {'name': 'Developer', 'status': 'active'})
        
        # Create overlapping assignments
        assignment1 = create_mock_object('assign_1', 'ot_assignment', {
            'person_id': 'person_1',
            'task_id': 'task_1',
            'allocation_percent': 80,
            'planned_start': datetime.utcnow().isoformat(),
            'planned_end': (datetime.utcnow() + timedelta(days=5)).isoformat()
        })
        
        assignment2 = create_mock_object('assign_2', 'ot_assignment', {
            'person_id': 'person_1',
            'task_id': 'task_2',
            'allocation_percent': 50,  # Total: 130% > 100%
            'planned_start': datetime.utcnow().isoformat(),
            'planned_end': (datetime.utcnow() + timedelta(days=5)).isoformat()
        })
        
        detector.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        detector.get_objects_by_type = MagicMock(return_value=[person])
        detector._get_person_assignments = MagicMock(return_value=[assignment1, assignment2])
        detector._calculate_daily_allocations = MagicMock(return_value={
            '2026-03-01': 130.0
        })
        
        conflicts = await detector.detect_overallocations()
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.OVERALLOCATION
        assert conflicts[0].allocation_percentage == 130.0
    
    @pytest.mark.asyncio
    async def test_detect_skill_mismatches(self, detector, mock_session):
        """Test skill mismatch detection."""
        person = create_mock_object('person_1', 'ot_person', {'name': 'Developer'})
        task = create_mock_object('task_1', 'ot_task', {'title': 'React Task', 'status': 'todo'})
        
        # Task requires React skill level 3
        skill_req = create_mock_object('req_1', 'ot_task_skill_requirement', {
            'task_id': 'task_1',
            'skill_id': 'skill_react',
            'minimum_proficiency': 3,
            'is_mandatory': True
        })
        
        # Person has React skill level 1 (below required)
        person_skill = create_mock_object('ps_1', 'ot_person_skill', {
            'person_id': 'person_1',
            'skill_id': 'skill_react',
            'proficiency_level': 1
        })
        
        skill = create_mock_object('skill_react', 'ot_skill', {'name': 'React'})
        
        assignment = create_mock_object('assign_1', 'ot_assignment', {
            'person_id': 'person_1',
            'task_id': 'task_1',
            'status': 'active'
        })
        
        detector.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        detector.get_linked_objects = MagicMock(side_effect=lambda s, id, **kwargs: {
            ('assign_1', 'lt_assignment_to_person'): [{'object': person}],
            ('task_1', 'lt_task_requires_skill'): [{'object': skill_req, 'link_data': {}}],
            ('person_1', 'lt_person_has_skill'): [{'object': person_skill, 'link_data': {'proficiency_level': 1}}]
        }.get((id, kwargs.get('link_type_id')), []))
        detector.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'task_1': task,
            'person_1': person,
            'skill_react': skill
        }.get(id))
        
        from sqlalchemy import select, and_
        mock_session.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[assignment])))
        
        conflicts = await detector.detect_skill_mismatches()
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.SKILL_MISMATCH
        assert 'React' in conflicts[0].description
    
    @pytest.mark.asyncio
    async def test_detect_sprint_overcommitments(self, detector, mock_session):
        """Test sprint overcommitment detection."""
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Overcommitted Sprint',
            'status': 'active'
        })
        
        # Sprint has tasks exceeding capacity
        sprint_task = create_mock_object('st_1', 'ot_sprint_task', {
            'sprint_id': 'sprint_1',
            'task_id': 'task_1'
        })
        
        task = create_mock_object('task_1', 'ot_task', {
            'estimated_hours': 100
        })
        
        detector.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        detector.get_objects_by_type = MagicMock(return_value=[sprint])
        detector._get_sprint_tasks = MagicMock(return_value=[task])
        detector._get_sprint_participants = MagicMock(return_value=[
            {'planned_capacity_hours': 40}  # Only 40h capacity but 100h committed
        ])
        
        conflicts = await detector.detect_sprint_overcommitments()
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.SPRINT_OVERCOMMITMENT
        assert conflicts[0].sprint_id == 'sprint_1'


# =============================================================================
# Agent Tools Tests
# =============================================================================

class TestAgentTools:
    """Tests for Agent Tools."""
    
    @pytest.mark.asyncio
    async def test_query_projects(self, mock_db_adapter, mock_session):
        """Test project query tool."""
        from extensions.project_management.agent_tools.query_tools import query_projects
        
        base = Mock()
        base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Test Project',
            'status': 'active',
            'priority_score': 80,
            'customer_id': 'cust_1'
        })
        
        mock_session.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[project])))
        
        with patch('extensions.project_management.agent_tools.query_tools.SchedulerBase') as MockBase:
            MockBase.return_value = base
            base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
            
            result = await query_projects(mock_db_adapter, filter={'status': 'active'}, limit=10)
            
            assert 'projects' in result
            assert result['count'] >= 0
    
    @pytest.mark.asyncio
    async def test_get_project_health(self, mock_db_adapter, mock_session):
        """Test project health tool."""
        from extensions.project_management.agent_tools.query_tools import get_project_health
        
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Test Project',
            'status': 'active',
            'risk_score': 30
        })
        
        base = Mock()
        base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        base.get_object_by_id = MagicMock(return_value=project)
        base.get_linked_objects = MagicMock(return_value=[
            {'object': create_mock_object('task_1', 'ot_task', {'status': 'done', 'estimated_hours': 8, 'actual_hours': 8})},
            {'object': create_mock_object('task_2', 'ot_task', {'status': 'in_progress', 'estimated_hours': 8})}
        ])
        
        with patch('extensions.project_management.agent_tools.query_tools.SchedulerBase') as MockBase:
            MockBase.return_value = base
            
            result = await get_project_health(mock_db_adapter, 'proj_1')
            
            assert result['project_id'] == 'proj_1'
            assert 'health_score' in result
            assert 'metrics' in result
    
    @pytest.mark.asyncio
    async def test_create_nudge(self, mock_db_adapter, mock_session):
        """Test create nudge tool."""
        from extensions.project_management.agent_tools.action_tools import create_nudge
        
        person = create_mock_object('person_1', 'ot_person', {'name': 'Developer'})
        
        base = Mock()
        base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        base.get_object_by_id = MagicMock(return_value=person)
        
        with patch('extensions.project_management.agent_tools.action_tools.SchedulerBase') as MockBase:
            MockBase.return_value = base
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            
            result = await create_nudge(
                mock_db_adapter,
                type='risk',
                title='Test Nudge',
                description='This is a test',
                recipient_ids=['person_1']
            )
            
            assert result['success'] is True
            assert result['nudges_created'] == 1


# =============================================================================
# Fixtures and Helpers
# =============================================================================

@pytest.fixture
def mock_db_adapter():
    return Mock()

@pytest.fixture
def mock_neo4j_adapter():
    return Mock()

@pytest.fixture
def mock_session():
    return MagicMock()

def create_mock_object(obj_id, type_id, data, status='active'):
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    return obj


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
