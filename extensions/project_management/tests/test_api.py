"""
Tests for Phase 4 API Endpoints

Tests cover all PM-specific API endpoints.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

# Import the router
from extensions.project_management.api import router as pm_router


# =============================================================================
# Fixtures
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


@pytest.fixture
def mock_current_user():
    user = Mock()
    user.id = "user_123"
    user.email = "pm@example.com"
    return user


def create_mock_object(obj_id, type_id, data, status='active'):
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    obj.created_at = datetime.utcnow()
    return obj


# =============================================================================
# Dashboard Endpoint Tests
# =============================================================================

class TestDashboardEndpoints:
    """Tests for dashboard endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_portfolio_overview(self, mock_db_adapter, mock_session):
        """Test portfolio overview endpoint."""
        from extensions.project_management.api.dashboard import get_portfolio_overview
        
        # Setup mock
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Test Project',
            'status': 'active',
            'priority_score': 80,
            'health_status': 'green',
            'customer_id': 'cust_1'
        })
        
        with patch('extensions.project_management.api.dashboard.SchedulerBase') as MockBase:
            base = Mock()
            base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
            MockBase.return_value = base
            
            with patch('extensions.project_management.api.dashboard.query_projects') as mock_query:
                mock_query.return_value = {
                    'projects': [{
                        'id': project.id,
                        'name': project.data['name'],
                        'status': project.data['status'],
                        'priority_score': project.data['priority_score'],
                        'health_status': project.data['health_status']
                    }]
                }
                
                result = await get_portfolio_overview(
                    db=mock_session,
                    current_user=Mock(id='user_123'),
                    _auth=True
                )
                
                assert 'summary' in result
                assert result['summary']['total_projects'] == 1
                assert 'projects' in result
                
    @pytest.mark.asyncio
    async def test_get_risk_dashboard(self, mock_db_adapter, mock_session):
        """Test risk dashboard endpoint."""
        from extensions.project_management.api.dashboard import get_risk_dashboard
        
        with patch('extensions.project_management.api.dashboard.SchedulerBase'):
            with patch('extensions.project_management.api.dashboard.query_tasks') as mock_tasks:
                mock_tasks.return_value = {
                    'tasks': [{
                        'id': 'task_1',
                        'title': 'At Risk Task',
                        'predicted_delay_probability': 0.8,
                        'project_id': 'proj_1'
                    }]
                }
                
                result = await get_risk_dashboard(
                    db=mock_session,
                    current_user=Mock(id='user_123'),
                    _auth=True,
                    severity='high'
                )
                
                assert 'risks' in result
                assert 'summary' in result


# =============================================================================
# Projects Endpoint Tests
# =============================================================================

class TestProjectsEndpoints:
    """Tests for projects endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_project_health(self, mock_db_adapter, mock_session):
        """Test project health endpoint."""
        from extensions.project_management.api.projects import get_project_health_endpoint
        
        with patch('extensions.project_management.api.projects.get_project_health') as mock_health:
            mock_health.return_value = {
                'project_id': 'proj_1',
                'health_score': 85,
                'status': 'healthy',
                'metrics': {'total_tasks': 10, 'completed_tasks': 5}
            }
            
            result = await get_project_health_endpoint(
                project_id='proj_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result['health_score'] == 85
            assert result['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_analyze_scope_change_impact(self, mock_db_adapter, mock_session):
        """Test scope change impact endpoint."""
        from extensions.project_management.api.projects import analyze_scope_change_impact
        from extensions.project_management.api.projects import ScopeChangeRequest
        
        request = ScopeChangeRequest(
            added_tasks=[{'title': 'New Feature', 'estimated_hours': 40}],
            removed_task_ids=[]
        )
        
        with patch('extensions.project_management.api.projects.simulate_scope_change') as mock_sim:
            mock_sim.return_value = {
                'impact_assessment': {'impact_level': 'medium', 'timeline_delay_days': 5},
                'can_commit': True,
                'current_state': {'total_hours': 100},
                'projected_state': {'total_hours': 140}
            }
            
            result = await analyze_scope_change_impact(
                project_id='proj_1',
                request=request,
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result.impact_level == 'medium'
            assert result.can_commit is True


# =============================================================================
# Tasks Endpoint Tests
# =============================================================================

class TestTasksEndpoints:
    """Tests for tasks endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_task_skill_matches(self, mock_db_adapter, mock_session):
        """Test task skill matches endpoint."""
        from extensions.project_management.api.tasks import get_task_skill_matches
        
        with patch('extensions.project_management.api.tasks.find_skill_matches') as mock_matches:
            mock_matches.return_value = {
                'task_id': 'task_1',
                'matches': [
                    {'person_id': 'person_1', 'person_name': 'Developer', 'match_score': 95}
                ],
                'has_perfect_match': True
            }
            
            result = await get_task_skill_matches(
                task_id='task_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True,
                limit=5
            )
            
            assert result['task_id'] == 'task_1'
            assert len(result['matches']) == 1
            assert result['has_perfect_match'] is True
    
    @pytest.mark.asyncio
    async def test_reassign_task_endpoint(self, mock_db_adapter, mock_session):
        """Test task reassignment endpoint."""
        from extensions.project_management.api.tasks import reassign_task_endpoint
        from extensions.project_management.api.tasks import ReassignRequest
        
        request = ReassignRequest(
            to_person_id='person_2',
            from_person_id='person_1',
            reason='Better skill match'
        )
        
        with patch('extensions.project_management.api.tasks.reassign_task') as mock_reassign:
            mock_reassign.return_value = {
                'success': True,
                'task_id': 'task_1',
                'assignment_id': 'assign_2',
                'changes': {'from_person_id': 'person_1', 'to_person_id': 'person_2'}
            }
            
            result = await reassign_task_endpoint(
                task_id='task_1',
                request=request,
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result.success is True
            assert result.task_id == 'task_1'


# =============================================================================
# Resources Endpoint Tests
# =============================================================================

class TestResourcesEndpoints:
    """Tests for resources endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_all_allocations(self, mock_db_adapter, mock_session):
        """Test allocations endpoint."""
        from extensions.project_management.api.resources import get_all_allocations
        
        with patch('extensions.project_management.api.resources.SchedulerBase') as MockBase:
            base = Mock()
            base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
            MockBase.return_value = base
            
            result = await get_all_allocations(
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert 'allocations' in result
            assert 'count' in result
    
    @pytest.mark.asyncio
    async def test_get_person_utilization(self, mock_db_adapter, mock_session):
        """Test person utilization endpoint."""
        from extensions.project_management.api.resources import get_person_utilization_endpoint
        
        with patch('extensions.project_management.api.resources.get_person_utilization') as mock_util:
            mock_util.return_value = {
                'person_id': 'person_1',
                'person_name': 'Developer',
                'utilization': {'average': 85, 'maximum': 100},
                'status': 'optimal'
            }
            
            result = await get_person_utilization_endpoint(
                person_id='person_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True,
                start_date='2026-03-01',
                end_date='2026-03-31'
            )
            
            assert result['person_id'] == 'person_1'
            assert result['utilization']['average'] == 85


# =============================================================================
# Sprints Endpoint Tests
# =============================================================================

class TestSprintsEndpoints:
    """Tests for sprints endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_sprint_recommendations(self, mock_db_adapter, mock_session):
        """Test sprint recommendations endpoint."""
        from extensions.project_management.api.sprints import get_sprint_recommendations_endpoint
        
        with patch('extensions.project_management.api.sprints.get_sprint_recommendations') as mock_rec:
            mock_rec.return_value = {
                'sprint_id': 'sprint_1',
                'recommended_tasks': [{'task_id': 'task_1', 'title': 'Feature A'}],
                'total_value_score': 250,
                'capacity': {'total_hours': 160, 'recommended_commitment': 136}
            }
            
            result = await get_sprint_recommendations_endpoint(
                sprint_id='sprint_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result['sprint_id'] == 'sprint_1'
            assert 'recommended_tasks' in result
    
    @pytest.mark.asyncio
    async def test_get_sprint_health(self, mock_db_adapter, mock_session):
        """Test sprint health endpoint."""
        from extensions.project_management.api.sprints import get_sprint_health_endpoint
        
        with patch('extensions.project_management.api.sprints.SprintPlanner') as MockPlanner:
            planner = Mock()
            health = Mock()
            health.sprint_id = 'sprint_1'
            health.status.value = 'good'
            health.health_score = 85
            health.completion_percentage = 60
            health.blocked_tasks_count = 1
            health.recommendations = ['Resolve blocked tasks']
            health.team_utilization = {}
            health.issues = []
            health.progress = Mock()
            health.progress.completion_percentage = 60
            
            planner.check_sprint_health = MagicMock(return_value=health)
            MockPlanner.return_value = planner
            
            result = await get_sprint_health_endpoint(
                sprint_id='sprint_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result['sprint_id'] == 'sprint_1'
            assert result['status'] == 'good'


# =============================================================================
# Simulation Endpoint Tests
# =============================================================================

class TestSimulationEndpoints:
    """Tests for simulation endpoints."""
    
    @pytest.mark.asyncio
    async def test_simulate_leave(self, mock_db_adapter, mock_session):
        """Test leave simulation endpoint."""
        from extensions.project_management.api.simulation import simulate_leave
        from extensions.project_management.api.simulation import LeaveSimulationRequest
        
        request = LeaveSimulationRequest(
            person_id='person_1',
            start_date='2026-03-01',
            end_date='2026-03-05',
            leave_type='vacation'
        )
        
        with patch('extensions.project_management.api.simulation.ImpactAnalyzer') as MockAnalyzer:
            analyzer = Mock()
            report = Mock()
            report.impact_level.value = 'medium'
            report.summary = '3 tasks affected'
            report.affected_projects = []
            report.affected_tasks = [{'task_id': 'task_1'}]
            report.total_delay_days = 2
            report.alternative_resources = []
            report.recommended_actions = []
            report.cost_impact = {}
            report.parameters = {'person_name': 'Developer'}
            
            analyzer.analyze_leave_impact = MagicMock(return_value=report)
            MockAnalyzer.return_value = analyzer
            
            result = await simulate_leave(
                request=request,
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result['simulation_type'] == 'leave'
            assert 'impact' in result


# =============================================================================
# Reports Endpoint Tests
# =============================================================================

class TestReportsEndpoints:
    """Tests for reports endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_portfolio_report(self, mock_db_adapter, mock_session):
        """Test portfolio report endpoint."""
        from extensions.project_management.api.reports import get_portfolio_report
        
        with patch('extensions.project_management.api.reports.SchedulerBase'):
            with patch('extensions.project_management.api.reports.query_projects') as mock_query:
                mock_query.return_value = {
                    'projects': [
                        {'id': 'proj_1', 'name': 'Project A', 'status': 'active', 'health_status': 'green'},
                        {'id': 'proj_2', 'name': 'Project B', 'status': 'active', 'health_status': 'yellow'}
                    ]
                }
                
                result = await get_portfolio_report(
                    db=mock_session,
                    current_user=Mock(id='user_123'),
                    _auth=True,
                    period='monthly'
                )
                
                assert result['report_type'] == 'portfolio'
                assert result['summary']['total_projects'] == 2


# =============================================================================
# Nudges Endpoint Tests
# =============================================================================

class TestNudgesEndpoints:
    """Tests for nudges endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_nudges(self, mock_db_adapter, mock_session):
        """Test list nudges endpoint."""
        from extensions.project_management.api.nudges import list_nudges
        
        with patch('extensions.project_management.api.nudges.SchedulerBase') as MockBase:
            base = Mock()
            base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
            MockBase.return_value = base
            
            result = await list_nudges(
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True,
                for_me=True
            )
            
            assert 'nudges' in result
            assert 'count' in result
    
    @pytest.mark.asyncio
    async def test_acknowledge_nudge(self, mock_db_adapter, mock_session):
        """Test acknowledge nudge endpoint."""
        from extensions.project_management.api.nudges import acknowledge_nudge
        from extensions.project_management.api.nudges import NudgeResponse
        
        with patch('extensions.project_management.api.nudges.SchedulerBase') as MockBase:
            base = Mock()
            nudge = create_mock_object('nudge_1', 'ot_nudge', {
                'recipient_id': 'user_123',
                'status': 'new'
            })
            base.get_object_by_id = MagicMock(return_value=nudge)
            base.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
            MockBase.return_value = base
            
            result = await acknowledge_nudge(
                nudge_id='nudge_1',
                db=mock_session,
                current_user=Mock(id='user_123'),
                _auth=True
            )
            
            assert result.success is True
            assert result.new_status == 'acknowledged'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
