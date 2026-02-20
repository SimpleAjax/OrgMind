"""
Pytest configuration and shared fixtures for Project Management Extension tests.
"""

import pytest
from unittest.mock import Mock, MagicMock
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_db_adapter():
    """Create a mock database adapter."""
    adapter = Mock()
    adapter.get_session = MagicMock()
    return adapter


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
    session.add = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    user = Mock()
    user.id = "user_123"
    user.email = "pm@example.com"
    user.name = "Test PM"
    user.role = "project_manager"
    return user


# =============================================================================
# Object Creation Helpers
# =============================================================================

def create_mock_object(obj_id: str, type_id: str, data: dict, status: str = 'active'):
    """Helper to create mock object models."""
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    obj.created_at = __import__('datetime').datetime.utcnow()
    obj.updated_at = __import__('datetime').datetime.utcnow()
    return obj


@pytest.fixture
def create_object():
    """Fixture to create mock objects."""
    return create_mock_object


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_customer():
    """Create a sample customer."""
    return create_mock_object('cust_1', 'ot_customer', {
        'name': 'Acme Corporation',
        'tier': 'tier_1',
        'contract_value': 500000,
        'sla_level': 'premium',
        'contact_email': 'contact@acme.com'
    })


@pytest.fixture
def sample_project():
    """Create a sample project."""
    return create_mock_object('proj_1', 'ot_project', {
        'name': 'Website Redesign',
        'description': 'Complete website redesign project',
        'status': 'active',
        'planned_start': '2026-01-01T00:00:00',
        'planned_end': '2026-06-30T00:00:00',
        'budget_hours': 800,
        'priority_score': 85,
        'risk_score': 25,
        'customer_id': 'cust_1'
    })


@pytest.fixture
def sample_sprint():
    """Create a sample sprint."""
    from datetime import datetime, timedelta
    return create_mock_object('sprint_1', 'ot_sprint', {
        'name': 'Sprint 1',
        'start_date': datetime.utcnow().isoformat(),
        'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat(),
        'total_capacity_hours': 320,
        'committed_hours': 272,  # 85% of capacity
        'status': 'active'
    })


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return create_mock_object('task_1', 'ot_task', {
        'title': 'Implement Login Page',
        'description': 'Create login page with form validation',
        'type': 'feature',
        'status': 'in_progress',
        'priority': 'high',
        'estimated_hours': 16,
        'actual_hours': 8,
        'project_id': 'proj_1',
        'predicted_delay_probability': 0.2
    })


@pytest.fixture
def sample_person():
    """Create a sample person."""
    return create_mock_object('person_1', 'ot_person', {
        'name': 'John Developer',
        'email': 'john@example.com',
        'role': 'senior_developer',
        'status': 'active',
        'working_hours_per_day': 8,
        'default_availability_percent': 100
    })


@pytest.fixture
def sample_skill():
    """Create a sample skill."""
    return create_mock_object('skill_react', 'ot_skill', {
        'name': 'React',
        'category': 'technical',
        'description': 'React.js frontend framework'
    })


@pytest.fixture
def sample_assignment():
    """Create a sample assignment."""
    return create_mock_object('assign_1', 'ot_assignment', {
        'person_id': 'person_1',
        'task_id': 'task_1',
        'allocation_percent': 50,
        'planned_start': '2026-03-01T00:00:00',
        'planned_end': '2026-03-05T00:00:00',
        'planned_hours': 16,
        'status': 'active'
    })


@pytest.fixture
def sample_nudge():
    """Create a sample nudge."""
    return create_mock_object('nudge_1', 'ot_nudge', {
        'type': 'risk',
        'severity': 'warning',
        'title': 'Task at risk of delay',
        'description': 'Task is 80% likely to miss deadline',
        'recipient_id': 'person_1',
        'related_task_id': 'task_1',
        'related_project_id': 'proj_1',
        'status': 'new',
        'context_data': {
            'delay_probability': 0.8,
            'days_remaining': 2
        }
    })


# =============================================================================
# Test Markers
# =============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "benchmark: Benchmark tests")


# =============================================================================
# Test Session Hooks
# =============================================================================

def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    print("\n" + "="*60)
    print("Project Management Extension Test Suite")
    print("="*60)


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    print("\n" + "="*60)
    if exitstatus == 0:
        print("All tests passed!")
    else:
        print(f"Tests failed with exit code: {exitstatus}")
    print("="*60)


# =============================================================================
# Async Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
