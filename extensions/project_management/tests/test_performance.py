"""
Performance and Load Tests for Project Management Extension

Tests cover:
- Scheduler performance under load
- API endpoint response times
- Database query performance
- Concurrent operation handling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any
import uuid

from extensions.project_management.schedulers import (
    PriorityCalculator,
    ImpactAnalyzer,
    NudgeGenerator,
    SkillMatcher,
    SprintPlanner,
    VelocityCalculator,
    ConflictDetector
)


# =============================================================================
# Performance Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db_adapter():
    """Create a mock database adapter."""
    return Mock()


@pytest.fixture
def mock_neo4j_adapter():
    """Create a mock Neo4j adapter."""
    adapter = Mock()
    adapter.execute_read = MagicMock(return_value=[])
    adapter.execute_write = MagicMock(return_value=[])
    return adapter


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.scalars = MagicMock()
    session.commit = MagicMock()
    return session


def create_mock_object(obj_id: str, type_id: str, data: dict, status: str = 'active'):
    """Helper to create mock object models."""
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    return obj


def generate_test_projects(count: int) -> List[Mock]:
    """Generate a specified number of mock projects for testing."""
    projects = []
    tiers = ['tier_1', 'tier_2', 'tier_3']
    
    for i in range(count):
        project = create_mock_object(
            f'proj_{i}',
            'ot_project',
            {
                'name': f'Project {i}',
                'customer_id': f'cust_{i % 10}',
                'planned_end': (datetime.utcnow() + timedelta(days=14 + (i % 60))).isoformat(),
                'business_value_score': 50 + (i % 50),
                'strategic_importance': 50 + (i % 40),
                'risk_score': i % 30,
                'contract_value': 10000 + (i * 1000),
                'status': 'active'
            }
        )
        projects.append(project)
    
    return projects


def generate_test_tasks(count: int, project_ids: List[str]) -> List[Mock]:
    """Generate a specified number of mock tasks for testing."""
    tasks = []
    statuses = ['todo', 'in_progress', 'done', 'blocked']
    
    for i in range(count):
        task = create_mock_object(
            f'task_{i}',
            'ot_task',
            {
                'title': f'Task {i}',
                'project_id': project_ids[i % len(project_ids)],
                'status': statuses[i % len(statuses)],
                'estimated_hours': 4 + (i % 20),
                'actual_hours': 4 + (i % 18) if statuses[i % len(statuses)] == 'done' else 0,
                'priority_score': 50 + (i % 50),
                'predicted_delay_probability': (i % 10) / 10,
                'due_date': (datetime.utcnow() + timedelta(days=7 + (i % 30))).isoformat()
            }
        )
        tasks.append(task)
    
    return tasks


def generate_test_people(count: int) -> List[Mock]:
    """Generate a specified number of mock people for testing."""
    people = []
    
    for i in range(count):
        person = create_mock_object(
            f'person_{i}',
            'ot_person',
            {
                'name': f'Person {i}',
                'email': f'person{i}@example.com',
                'role': 'developer' if i % 3 == 0 else 'designer' if i % 3 == 1 else 'manager',
                'status': 'active',
                'working_hours_per_day': 8,
                'default_availability_percent': 100
            }
        )
        people.append(person)
    
    return people


# =============================================================================
# Priority Calculator Performance Tests
# =============================================================================

class TestPriorityCalculatorPerformance:
    """Performance tests for PriorityCalculator."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_calculate_priority_100_projects_under_5_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that calculating priority for 100 projects completes within 5 seconds."""
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        
        # Generate 100 test projects
        projects = generate_test_projects(100)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        # Measure execution time
        start_time = time.time()
        result = await calculator.recalculate_all_priorities()
        elapsed_time = time.time() - start_time
        
        # Assert performance requirements
        assert result['processed'] == 100
        assert elapsed_time < 5.0, f"Priority calculation took {elapsed_time:.2f}s, expected < 5s"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_batch_priority_update_performance(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test batch priority update performance."""
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        
        # Generate 50 test projects
        projects = generate_test_projects(50)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        # Run multiple times to measure consistency
        times = []
        for _ in range(3):
            start_time = time.time()
            await calculator.recalculate_all_priorities()
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        # Assert consistent performance
        assert avg_time < 3.0, f"Average time {avg_time:.2f}s exceeds threshold"
        assert max_time < 5.0, f"Max time {max_time:.2f}s exceeds threshold"


# =============================================================================
# Impact Analyzer Performance Tests
# =============================================================================

class TestImpactAnalyzerPerformance:
    """Performance tests for ImpactAnalyzer."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_leave_impact_analysis_under_5_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that leave impact analysis completes within 5 seconds."""
        analyzer = ImpactAnalyzer(mock_db_adapter, mock_neo4j_adapter)
        
        # Setup person with 20 assignments
        person = create_mock_object('person_1', 'ot_person', {
            'name': 'Test Person',
            'status': 'active'
        })
        
        assignments = []
        for i in range(20):
            task = create_mock_object(f'task_{i}', 'ot_task', {
                'title': f'Task {i}',
                'project_id': f'proj_{i % 5}',
                'estimated_hours': 16,
                'status': 'in_progress'
            })
            assignments.append({
                'task': task,
                'allocation': 50
            })
        
        analyzer.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        analyzer.get_object_by_id = MagicMock(return_value=person)
        analyzer._get_assignments_during_period = MagicMock(return_value=assignments)
        analyzer._is_on_critical_path = MagicMock(return_value=False)
        
        # Measure execution time
        start_time = time.time()
        result = await analyzer.analyze_leave_impact(
            person_id='person_1',
            start_date='2026-03-01',
            end_date='2026-03-05',
            leave_type='vacation'
        )
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 5.0, f"Leave impact analysis took {elapsed_time:.2f}s"
        assert result.impact_type == 'leave'
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_scope_change_impact_under_3_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that scope change impact analysis completes within 3 seconds."""
        analyzer = ImpactAnalyzer(mock_db_adapter, mock_neo4j_adapter)
        
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Test Project',
            'planned_end': '2026-06-01',
            'hourly_rate': 100
        })
        
        # Create 30 tasks to analyze
        dependent_tasks = [
            create_mock_object(f'task_{i}', 'ot_task', {
                'title': f'Dependent Task {i}',
                'estimated_hours': 8,
                'status': 'todo'
            })
            for i in range(30)
        ]
        
        analyzer.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        analyzer.get_object_by_id = MagicMock(return_value=project)
        analyzer.get_linked_objects = MagicMock(return_value=[
            {'object': task, 'link_data': {}} for task in dependent_tasks
        ])
        
        added_tasks = [
            {'title': f'New Feature {i}', 'estimated_hours': 40}
            for i in range(10)
        ]
        
        start_time = time.time()
        result = await analyzer.analyze_scope_change_impact(
            project_id='proj_1',
            added_tasks=added_tasks,
            removed_tasks=[]
        )
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 3.0, f"Scope change impact took {elapsed_time:.2f}s"


# =============================================================================
# Sprint Planner Performance Tests
# =============================================================================

class TestSprintPlannerPerformance:
    """Performance tests for SprintPlanner."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_sprint_planning_50_tasks_under_3_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that sprint planning with 50 tasks completes within 3 seconds."""
        planner = SprintPlanner(mock_db_adapter, mock_neo4j_adapter)
        
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': datetime.utcnow().isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat()
        })
        
        # Generate 50 available tasks
        available_tasks = generate_test_tasks(50, ['proj_1', 'proj_2', 'proj_3'])
        
        planner.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': f'person_{i}', 'name': f'Dev {i}', 'planned_capacity_hours': 80}
            for i in range(5)
        ])
        planner._get_available_tasks = MagicMock(return_value=available_tasks)
        planner._find_best_assignee = MagicMock(return_value=('person_1', 85.0))
        planner._calculate_dependency_risk = MagicMock(return_value=10)
        
        start_time = time.time()
        recommendation = await planner.generate_sprint_recommendation('sprint_1')
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 3.0, f"Sprint planning took {elapsed_time:.2f}s"
        assert len(recommendation.recommended_tasks) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_sprint_health_check_under_2_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that sprint health check completes within 2 seconds."""
        planner = SprintPlanner(mock_db_adapter, mock_neo4j_adapter)
        
        sprint = create_mock_object('sprint_1', 'ot_sprint', {
            'name': 'Sprint 1',
            'start_date': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=7)).isoformat()
        })
        
        # Generate 40 sprint tasks
        sprint_tasks = generate_test_tasks(40, ['proj_1'])
        
        planner.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        planner.get_object_by_id = MagicMock(return_value=sprint)
        planner._get_sprint_tasks = MagicMock(return_value=sprint_tasks)
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': f'person_{i}', 'name': f'Dev {i}', 'planned_capacity_hours': 80}
            for i in range(4)
        ])
        planner._calculate_team_utilization = MagicMock(return_value={
            f'person_{i}': 75 for i in range(4)
        })
        
        start_time = time.time()
        health = await planner.check_sprint_health('sprint_1')
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 2.0, f"Health check took {elapsed_time:.2f}s"
        assert health.sprint_id == 'sprint_1'


# =============================================================================
# Conflict Detector Performance Tests
# =============================================================================

class TestConflictDetectorPerformance:
    """Performance tests for ConflictDetector."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_conflict_detection_200_resources_under_30_seconds(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that conflict detection for 200 resources completes within 30 seconds."""
        detector = ConflictDetector(mock_db_adapter, mock_neo4j_adapter)
        
        # Generate 200 people
        people = generate_test_people(200)
        
        # Generate assignments for each person
        def mock_get_assignments(session, person_id):
            assignments = []
            for i in range(3):  # 3 assignments per person
                assignment = create_mock_object(
                    f'assign_{person_id}_{i}',
                    'ot_assignment',
                    {
                        'person_id': person_id,
                        'task_id': f'task_{i}',
                        'allocation_percent': 50,
                        'planned_start': datetime.utcnow().isoformat(),
                        'planned_end': (datetime.utcnow() + timedelta(days=5)).isoformat()
                    }
                )
                assignments.append(assignment)
            return assignments
        
        detector.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        detector.get_objects_by_type = MagicMock(return_value=people)
        detector._get_person_assignments = MagicMock(side_effect=mock_get_assignments)
        detector._calculate_daily_allocations = MagicMock(return_value={
            '2026-03-01': 150.0  # Overallocated
        })
        
        start_time = time.time()
        summary = await detector.detect_conflicts()
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 30.0, f"Conflict detection took {elapsed_time:.2f}s"
        assert summary.total_conflicts > 0


# =============================================================================
# Concurrent Operation Tests
# =============================================================================

class TestConcurrentOperations:
    """Tests for concurrent operation handling."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_priority_calculations(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test handling multiple concurrent priority calculations."""
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        
        projects = generate_test_projects(20)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_object_by_id = MagicMock(side_effect=lambda s, id: next(
            (p for p in projects if p.id == id), None
        ))
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        # Run 10 concurrent calculations
        start_time = time.time()
        tasks = [
            calculator.calculate_project_priority(f'proj_{i}', save=False)
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        elapsed_time = time.time() - start_time
        
        assert len(results) == 10
        assert elapsed_time < 5.0, f"Concurrent calculations took {elapsed_time:.2f}s"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_sprint_health_checks(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test handling multiple concurrent sprint health checks."""
        planner = SprintPlanner(mock_db_adapter, mock_neo4j_adapter)
        
        sprints = [
            create_mock_object(f'sprint_{i}', 'ot_sprint', {
                'name': f'Sprint {i}',
                'start_date': (datetime.utcnow() - timedelta(days=7)).isoformat(),
                'end_date': (datetime.utcnow() + timedelta(days=7)).isoformat()
            })
            for i in range(5)
        ]
        
        sprint_tasks = generate_test_tasks(20, ['proj_1'])
        
        planner.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        planner.get_object_by_id = MagicMock(side_effect=lambda s, id: next(
            (sp for sp in sprints if sp.id == id), None
        ))
        planner._get_sprint_tasks = MagicMock(return_value=sprint_tasks)
        planner._get_sprint_participants = MagicMock(return_value=[
            {'id': f'person_{i}', 'name': f'Dev {i}', 'planned_capacity_hours': 80}
            for i in range(3)
        ])
        planner._calculate_team_utilization = MagicMock(return_value={
            f'person_{i}': 75 for i in range(3)
        })
        
        # Run 5 concurrent health checks
        start_time = time.time()
        tasks = [planner.check_sprint_health(f'sprint_{i}') for i in range(5)]
        results = await asyncio.gather(*tasks)
        elapsed_time = time.time() - start_time
        
        assert len(results) == 5
        assert elapsed_time < 5.0, f"Concurrent health checks took {elapsed_time:.2f}s"


# =============================================================================
# Memory Usage Tests
# =============================================================================

class TestMemoryUsage:
    """Tests for memory efficiency."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_large_dataset_handling(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test handling of large datasets without excessive memory usage."""
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        
        # Generate 500 projects (large dataset)
        projects = generate_test_projects(500)
        
        calculator.get_session = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_session),
            __exit__=MagicMock()
        ))
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        # Should complete without memory issues
        result = await calculator.recalculate_all_priorities()
        
        assert result['processed'] == 500
        assert result['errors'] == 0


# =============================================================================
# Benchmark Tests
# =============================================================================

class TestBenchmarks:
    """Benchmark tests for establishing performance baselines."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_priority_calculation_benchmark(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Benchmark priority calculation performance."""
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        
        # Test with various dataset sizes
        sizes = [10, 50, 100]
        results = {}
        
        for size in sizes:
            projects = generate_test_projects(size)
            
            calculator.get_session = MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=mock_session),
                __exit__=MagicMock()
            ))
            calculator.get_objects_by_type = MagicMock(return_value=projects)
            calculator.get_object_by_id = MagicMock(return_value=None)
            calculator.update_object_data = MagicMock(return_value=projects[0])
            
            start_time = time.time()
            await calculator.recalculate_all_priorities()
            elapsed_time = time.time() - start_time
            
            results[size] = {
                'time': elapsed_time,
                'per_project': elapsed_time / size
            }
        
        # Log benchmark results
        print("\nPriority Calculation Benchmark:")
        for size, metrics in results.items():
            print(f"  {size} projects: {metrics['time']:.3f}s ({metrics['per_project']*1000:.1f}ms/project)")
        
        # Assert reasonable scaling
        assert results[100]['per_project'] < results[10]['per_project'] * 2  # Sub-linear scaling


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'performance'])
