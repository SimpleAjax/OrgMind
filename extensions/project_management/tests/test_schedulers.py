"""
Tests for Phase 2 Core Schedulers

Tests cover:
- PriorityCalculator
- ImpactAnalyzer
- NudgeGenerator
- SkillMatcher
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import uuid

# Import schedulers
from extensions.project_management.schedulers import (
    PriorityCalculator,
    ImpactAnalyzer,
    NudgeGenerator,
    SkillMatcher
)
from extensions.project_management.schedulers.priority_calculator import (
    PriorityComponents
)
from extensions.project_management.schedulers.nudge_generator import (
    NudgeCandidate, NudgeType, NudgeSeverity
)
from extensions.project_management.schedulers.skill_matcher import (
    SkillMatchResult
)


# =============================================================================
# Fixtures
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
    return session


def create_mock_object(
    obj_id: str,
    type_id: str,
    data: dict,
    status: str = 'active'
):
    """Helper to create mock object models."""
    obj = Mock()
    obj.id = obj_id
    obj.type_id = type_id
    obj.data = data
    obj.status = status
    obj.version = 1
    return obj


# =============================================================================
# Priority Calculator Tests
# =============================================================================

class TestPriorityCalculator:
    """Tests for PriorityCalculator."""
    
    @pytest.fixture
    def calculator(self, mock_db_adapter, mock_neo4j_adapter):
        """Create a PriorityCalculator instance."""
        return PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
    
    @pytest.mark.asyncio
    async def test_calculate_project_priority_basic(self, calculator, mock_session):
        """Test basic priority calculation."""
        # Setup mock project
        project_data = {
            'name': 'Test Project',
            'customer_id': 'cust_1',
            'planned_end': (datetime.utcnow() + timedelta(days=14)).isoformat(),
            'business_value_score': 80,
            'strategic_importance': 70,
            'risk_score': 20
        }
        project = create_mock_object('proj_1', 'ot_project', project_data)
        
        # Setup mock customer
        customer_data = {'name': 'Test Customer', 'tier': 'tier_1'}
        customer = create_mock_object('cust_1', 'ot_customer', customer_data)
        
        # Setup mocks
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        calculator.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'proj_1': project,
            'cust_1': customer
        }.get(id))
        calculator.get_objects_by_type = MagicMock(return_value=[project])
        
        # Calculate priority
        result = await calculator.calculate_project_priority('proj_1', save=False)
        
        # Verify result
        assert isinstance(result, PriorityComponents)
        assert 0 <= result.total_score <= 100
        assert result.customer_tier_score == 100  # tier_1 = 100
        assert result.business_value_score == 80
        assert result.strategic_importance_score == 70
    
    @pytest.mark.asyncio
    async def test_customer_tier_scoring(self, calculator, mock_session):
        """Test that customer tier affects priority correctly."""
        tiers = [
            ('tier_1', 100),
            ('tier_2', 75),
            ('tier_3', 50)
        ]
        
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        
        for tier, expected_score in tiers:
            customer = create_mock_object(f'cust_{tier}', 'ot_customer', {'tier': tier})
            
            project_data = {
                'name': f'Project {tier}',
                'customer_id': f'cust_{tier}',
                'planned_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'business_value_score': 50,
                'strategic_importance': 50
            }
            project = create_mock_object(f'proj_{tier}', 'ot_project', project_data)
            
            calculator.get_object_by_id = MagicMock(return_value=customer)
            calculator.get_objects_by_type = MagicMock(return_value=[project])
            
            result = await calculator.calculate_project_priority(f'proj_{tier}', save=False)
            
            assert result.customer_tier_score == expected_score, f"Tier {tier} should have score {expected_score}"
    
    @pytest.mark.asyncio
    async def test_deadline_proximity_scoring(self, calculator, mock_session):
        """Test deadline proximity scoring."""
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        
        deadlines = [
            (3, 100),   # Urgent (< 7 days)
            (14, 85),   # Warning range
            (45, 55),   # Planning range
            (120, 40)   # Far future
        ]
        
        for days, expected_range in deadlines:
            end_date = (datetime.utcnow() + timedelta(days=days)).isoformat()
            project_data = {
                'name': f'Project {days}d',
                'customer_id': None,
                'planned_end': end_date,
                'business_value_score': 50,
                'strategic_importance': 50
            }
            project = create_mock_object(f'proj_{days}', 'ot_project', project_data)
            
            calculator.get_object_by_id = MagicMock(return_value=None)
            calculator.get_objects_by_type = MagicMock(return_value=[project])
            
            result = await calculator.calculate_project_priority(f'proj_{days}', save=False)
            
            # Should be in expected range (with some tolerance)
            assert result.deadline_proximity_score >= expected_range - 15
            assert result.deadline_proximity_score <= expected_range + 15
    
    @pytest.mark.asyncio
    async def test_risk_penalty(self, calculator, mock_session):
        """Test that risk reduces priority score."""
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        
        project_data = {
            'name': 'Risky Project',
            'customer_id': None,
            'planned_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
            'business_value_score': 80,
            'strategic_importance': 80,
            'risk_score': 50  # High risk
        }
        project = create_mock_object('proj_risk', 'ot_project', project_data)
        
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.get_objects_by_type = MagicMock(return_value=[project])
        
        result = await calculator.calculate_project_priority('proj_risk', save=False)
        
        # Risk penalty should be 50 * 0.3 = 15 points
        assert result.risk_penalty == 15.0
    
    @pytest.mark.asyncio
    async def test_recalculate_all_priorities(self, calculator, mock_session):
        """Test batch priority recalculation."""
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        
        projects = [
            create_mock_object(f'proj_{i}', 'ot_project', {
                'name': f'Project {i}',
                'customer_id': None,
                'planned_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'business_value_score': 50 + i * 10,
                'strategic_importance': 50
            })
            for i in range(3)
        ]
        
        calculator.get_objects_by_type = MagicMock(return_value=projects)
        calculator.get_object_by_id = MagicMock(return_value=None)
        calculator.update_object_data = MagicMock(return_value=projects[0])
        
        result = await calculator.recalculate_all_priorities()
        
        assert result['processed'] == 3
        assert result['updated'] == 3
        assert 'statistics' in result
        assert result['errors'] == 0


# =============================================================================
# Impact Analyzer Tests
# =============================================================================

class TestImpactAnalyzer:
    """Tests for ImpactAnalyzer."""
    
    @pytest.fixture
    def analyzer(self, mock_db_adapter, mock_neo4j_adapter):
        """Create an ImpactAnalyzer instance."""
        return ImpactAnalyzer(mock_db_adapter, mock_neo4j_adapter)
    
    @pytest.mark.asyncio
    async def test_analyze_leave_impact_basic(self, analyzer, mock_session):
        """Test basic leave impact analysis."""
        # Setup
        person_data = {
            'name': 'John Doe',
            'status': 'active',
            'manager_id': 'mgr_1'
        }
        person = create_mock_object('person_1', 'ot_person', person_data)
        
        analyzer.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        analyzer.get_object_by_id = MagicMock(return_value=person)
        analyzer._get_assignments_during_period = MagicMock(return_value=[])
        analyzer._is_on_critical_path = MagicMock(return_value=False)
        
        # Execute
        result = await analyzer.analyze_leave_impact(
            person_id='person_1',
            start_date='2026-03-01',
            end_date='2026-03-05',
            leave_type='vacation'
        )
        
        # Verify
        assert result.impact_type == 'leave'
        assert result.related_people[0]['person_id'] == 'person_1'
        assert 'John Doe' in result.summary
    
    @pytest.mark.asyncio
    async def test_analyze_scope_change_impact(self, analyzer, mock_session):
        """Test scope change impact analysis."""
        project_data = {
            'name': 'Test Project',
            'planned_end': '2026-06-01',
            'hourly_rate': 100,
            'pm_id': 'pm_1'
        }
        project = create_mock_object('proj_1', 'ot_project', project_data)
        
        analyzer.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        analyzer.get_object_by_id = MagicMock(return_value=project)
        analyzer.get_linked_objects = MagicMock(return_value=[])
        
        added_tasks = [
            {'title': 'New Feature', 'estimated_hours': 40},
            {'title': 'Bug Fix', 'estimated_hours': 8}
        ]
        
        result = await analyzer.analyze_scope_change_impact(
            project_id='proj_1',
            added_tasks=added_tasks,
            removed_tasks=[]
        )
        
        assert result.impact_type == 'scope_change'
        assert result.affected_projects[0]['project_id'] == 'proj_1'
        assert result.cost_impact['additional_hours'] == 48
        assert len(result.recommended_actions) > 0
    
    @pytest.mark.asyncio
    async def test_find_alternative_resources(self, analyzer, mock_session):
        """Test finding alternative resources."""
        task_data = {
            'title': 'Development Task',
            'project_id': 'proj_1'
        }
        task = create_mock_object('task_1', 'ot_task', task_data)
        
        analyzer.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        analyzer.get_object_by_id = MagicMock(return_value=task)
        analyzer.get_linked_objects = MagicMock(return_value=[])
        analyzer.get_objects_by_type = MagicMock(return_value=[])
        analyzer._check_person_capacity = MagicMock(return_value=True)
        analyzer._calculate_skill_match = MagicMock(return_value={
            'score': 80,
            'matches': [],
            'missing': []
        })
        
        result = await analyzer.find_alternative_resources(
            task_id='task_1',
            exclude_person_id='person_1',
            limit=3
        )
        
        assert isinstance(result, list)


# =============================================================================
# Nudge Generator Tests
# =============================================================================

class TestNudgeGenerator:
    """Tests for NudgeGenerator."""
    
    @pytest.fixture
    def generator(self, mock_db_adapter, mock_neo4j_adapter):
        """Create a NudgeGenerator instance."""
        return NudgeGenerator(mock_db_adapter, mock_neo4j_adapter)
    
    @pytest.mark.asyncio
    async def test_detect_delay_risks(self, generator, mock_session):
        """Test delay risk detection."""
        # Setup at-risk tasks
        at_risk_task = create_mock_object('task_1', 'ot_task', {
            'title': 'Critical Task',
            'predicted_delay_probability': 0.85,
            'status': 'in_progress',
            'due_date': '2026-03-01',
            'project_id': 'proj_1'
        })
        
        safe_task = create_mock_object('task_2', 'ot_task', {
            'title': 'Safe Task',
            'predicted_delay_probability': 0.3,
            'status': 'in_progress',
            'project_id': 'proj_1'
        })
        
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Test Project',
            'pm_id': 'pm_1'
        })
        
        generator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        generator.get_objects_by_type = MagicMock(return_value=[at_risk_task, safe_task])
        generator.get_object_by_id = MagicMock(return_value=project)
        generator._get_task_assignees = MagicMock(return_value=[])
        
        # Execute
        candidates = await generator.detect_delay_risks()
        
        # Verify
        assert len(candidates) == 1  # Only at_risk_task
        assert candidates[0].type == NudgeType.RISK
        assert candidates[0].severity == NudgeSeverity.WARNING
        assert 'task_1' in candidates[0].related_task_id
    
    @pytest.mark.asyncio
    async def test_rank_nudges(self, generator):
        """Test nudge ranking."""
        nudges = [
            NudgeCandidate(
                type=NudgeType.RISK,
                severity=NudgeSeverity.INFO,
                title="Low Risk",
                description="Test",
                recipient_id="user_1",
                confidence=0.5
            ),
            NudgeCandidate(
                type=NudgeType.RISK,
                severity=NudgeSeverity.CRITICAL,
                title="Critical Risk",
                description="Test",
                recipient_id="user_1",
                confidence=0.9
            ),
            NudgeCandidate(
                type=NudgeType.OPPORTUNITY,
                severity=NudgeSeverity.INFO,
                title="Opportunity",
                description="Test",
                recipient_id="user_1",
                confidence=0.7
            )
        ]
        
        ranked = generator.rank_nudges(nudges)
        
        # Critical should be first
        assert ranked[0].severity == NudgeSeverity.CRITICAL
        # Risk should rank higher than opportunity at same severity
        assert ranked[1].type == NudgeType.RISK
    
    @pytest.mark.asyncio
    async def test_deduplicate_nudges(self, generator):
        """Test nudge deduplication."""
        nudges = [
            NudgeCandidate(
                type=NudgeType.RISK,
                severity=NudgeSeverity.WARNING,
                title="Duplicate Risk",
                description="Test 1",
                recipient_id="user_1",
                related_task_id="task_1"
            ),
            NudgeCandidate(
                type=NudgeType.RISK,
                severity=NudgeSeverity.WARNING,
                title="Duplicate Risk",
                description="Test 2",
                recipient_id="user_1",
                related_task_id="task_1"
            ),
            NudgeCandidate(
                type=NudgeType.RISK,
                severity=NudgeSeverity.WARNING,
                title="Different Risk",
                description="Test 3",
                recipient_id="user_1",
                related_task_id="task_2"
            )
        ]
        
        deduplicated = generator._deduplicate_nudges(nudges)
        
        assert len(deduplicated) == 2  # One duplicate removed
    
    @pytest.mark.asyncio
    async def test_detect_burnout_risks(self, generator, mock_session):
        """Test burnout risk detection."""
        overallocated_person = create_mock_object('person_1', 'ot_person', {
            'name': 'Overworked Employee',
            'status': 'active',
            'manager_id': 'mgr_1'
        })
        
        normal_person = create_mock_object('person_2', 'ot_person', {
            'name': 'Normal Employee',
            'status': 'active',
            'manager_id': 'mgr_1'
        })
        
        generator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        generator.get_objects_by_type = MagicMock(return_value=[overallocated_person, normal_person])
        generator._calculate_average_allocation = MagicMock(side_effect=lambda s, p, w: {
            'person_1': 95.0,
            'person_2': 70.0
        }.get(p, 0))
        
        candidates = await generator.detect_burnout_risks()
        
        assert len(candidates) == 1
        assert candidates[0].related_person_id == 'person_1'
        assert 'Overworked Employee' in candidates[0].title


# =============================================================================
# Skill Matcher Tests
# =============================================================================

class TestSkillMatcher:
    """Tests for SkillMatcher."""
    
    @pytest.fixture
    def matcher(self, mock_db_adapter):
        """Create a SkillMatcher instance."""
        return SkillMatcher(mock_db_adapter)
    
    @pytest.mark.asyncio
    async def test_find_best_matches_full_match(self, matcher, mock_session):
        """Test finding matches when person has all required skills."""
        # Setup task with skill requirements
        task = create_mock_object('task_1', 'ot_task', {
            'title': 'React Development',
            'project_id': 'proj_1'
        })
        
        # Setup skill requirement
        skill_req = create_mock_object('req_1', 'ot_task_skill_requirement', {
            'task_id': 'task_1',
            'skill_id': 'skill_react',
            'minimum_proficiency': 3,
            'is_mandatory': True
        })
        
        # Setup person with matching skill
        person = create_mock_object('person_1', 'ot_person', {
            'name': 'React Expert',
            'status': 'active'
        })
        
        person_skill = create_mock_object('ps_1', 'ot_person_skill', {
            'person_id': 'person_1',
            'skill_id': 'skill_react',
            'proficiency_level': 4  # Above required
        })
        
        skill = create_mock_object('skill_react', 'ot_skill', {
            'name': 'React',
            'category': 'technical'
        })
        
        matcher.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        matcher.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'task_1': task,
            'person_1': person,
            'skill_react': skill
        }.get(id))
        matcher.get_linked_objects = MagicMock(side_effect=lambda s, id, **kwargs: {
            ('task_1', 'lt_task_requires_skill'): [{'object': skill_req, 'link_data': {}}],
            ('person_1', 'lt_person_has_skill'): [{'object': person_skill, 'link_data': {'proficiency_level': 4}}]
        }.get((id, kwargs.get('link_type_id'))))
        matcher.get_objects_by_type = MagicMock(return_value=[person])
        matcher._calculate_availability = MagicMock(return_value=50.0)
        
        # Execute
        matches = await matcher.find_best_matches('task_1', limit=5)
        
        # Verify
        assert len(matches) == 1
        assert matches[0].match_score == 100.0
        assert matches[0].is_full_match is True
        assert len(matches[0].matching_skills) == 1
    
    @pytest.mark.asyncio
    async def test_calculate_skill_match_partial(self, matcher, mock_session):
        """Test skill match calculation for partial match."""
        task = create_mock_object('task_1', 'ot_task', {
            'title': 'Full Stack Task',
            'project_id': 'proj_1'
        })
        
        # Requires React (level 3) and Python (level 3)
        skill_reqs = [
            create_mock_object('req_1', 'ot_task_skill_requirement', {
                'skill_id': 'skill_react',
                'minimum_proficiency': 3,
                'is_mandatory': True
            }),
            create_mock_object('req_2', 'ot_task_skill_requirement', {
                'skill_id': 'skill_python',
                'minimum_proficiency': 3,
                'is_mandatory': True
            })
        ]
        
        # Person has React (level 4) but Python (level 2) - below required
        person = create_mock_object('person_1', 'ot_person', {
            'name': 'Partial Match',
            'status': 'active'
        })
        
        person_skills = [
            {'object': create_mock_object('ps_1', 'ot_person_skill', {
                'skill_id': 'skill_react'
            }), 'link_data': {'proficiency_level': 4}},
            {'object': create_mock_object('ps_2', 'ot_person_skill', {
                'skill_id': 'skill_python'
            }), 'link_data': {'proficiency_level': 2}}
        ]
        
        matcher.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        matcher.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'task_1': task,
            'person_1': person,
            'skill_react': create_mock_object('skill_react', 'ot_skill', {'name': 'React'}),
            'skill_python': create_mock_object('skill_python', 'ot_skill', {'name': 'Python'})
        }.get(id))
        matcher.get_linked_objects = MagicMock(side_effect=lambda s, id, **kwargs: {
            ('task_1', 'lt_task_requires_skill'): [
                {'object': skill_reqs[0], 'link_data': {}},
                {'object': skill_reqs[1], 'link_data': {}}
            ],
            ('person_1', 'lt_person_has_skill'): person_skills
        }.get((id, kwargs.get('link_type_id'))))
        matcher._calculate_availability = MagicMock(return_value=50.0)
        matcher._get_task_skill_requirements = MagicMock(return_value=[
            {'skill_id': 'skill_react', 'skill_name': 'React', 'skill_category': 'technical',
             'min_proficiency': 3, 'preferred_proficiency': 4, 'is_mandatory': True, 'weight': 2.0},
            {'skill_id': 'skill_python', 'skill_name': 'Python', 'skill_category': 'technical',
             'min_proficiency': 3, 'preferred_proficiency': 4, 'is_mandatory': True, 'weight': 2.0}
        ])
        
        result = await matcher.calculate_skill_match('person_1', 'task_1')
        
        # React: full match (4/3 = 1.0)
        # Python: partial (2/3 * 0.5 = 0.33)
        # Average: (1.0 + 0.33) / 2 = 0.665 -> 66.5%
        assert result.match_score < 100.0
        assert result.match_score > 50.0
        assert len(result.matching_skills) == 1  # Only React
        assert len(result.below_required) == 1  # Python below required
        assert result.is_full_match is False
    
    @pytest.mark.asyncio
    async def test_identify_skill_gaps(self, matcher, mock_session):
        """Test organization-wide skill gap identification."""
        # Multiple tasks require a rare skill
        skill_reqs = [
            create_mock_object(f'req_{i}', 'ot_task_skill_requirement', {
                'skill_id': 'skill_rust',
                'task_id': f'task_{i}',
                'minimum_proficiency': 3
            })
            for i in range(10)
        ]
        
        # Only 1 person has the skill
        person_skill = create_mock_object('ps_1', 'ot_person_skill', {
            'skill_id': 'skill_rust',
            'person_id': 'person_1',
            'proficiency_level': 4
        })
        
        skill = create_mock_object('skill_rust', 'ot_skill', {
            'name': 'Rust',
            'category': 'technical'
        })
        
        person = create_mock_object('person_1', 'ot_person', {
            'name': 'Rust Expert',
            'status': 'active'
        })
        
        matcher.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        matcher._get_all_skill_requirements = MagicMock(return_value=[
            {'skill_id': 'skill_rust', 'task_id': f'task_{i}', 'min_proficiency': 3, 'is_mandatory': True}
            for i in range(10)
        ])
        matcher.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'skill_rust': skill,
            'person_1': person
        }.get(id))
        matcher._count_qualified_people = MagicMock(return_value=1)
        
        gaps = await matcher.identify_skill_gaps()
        
        assert len(gaps) == 1
        assert gaps[0].skill_name == 'Rust'
        assert gaps[0].tasks_requiring == 10
        assert gaps[0].qualified_people == 1
        assert gaps[0].gap_severity in ['critical', 'high']


# =============================================================================
# Integration Tests
# =============================================================================

class TestSchedulerIntegration:
    """Integration tests for schedulers working together."""
    
    @pytest.mark.asyncio
    async def test_priority_impact_workflow(self, mock_db_adapter, mock_neo4j_adapter, mock_session):
        """Test that priority calculation and impact analysis work together."""
        # This tests the workflow described in the PRD
        
        calculator = PriorityCalculator(mock_db_adapter, mock_neo4j_adapter)
        analyzer = ImpactAnalyzer(mock_db_adapter, mock_neo4j_adapter)
        
        # Setup project with high priority
        project = create_mock_object('proj_1', 'ot_project', {
            'name': 'Critical Project',
            'customer_id': 'cust_1',
            'planned_end': (datetime.utcnow() + timedelta(days=7)).isoformat(),
            'business_value_score': 90,
            'strategic_importance': 85,
            'priority_score': 85
        })
        
        customer = create_mock_object('cust_1', 'ot_customer', {
            'name': 'VIP Customer',
            'tier': 'tier_1'
        })
        
        calculator.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        calculator.get_object_by_id = MagicMock(side_effect=lambda s, id: {
            'proj_1': project,
            'cust_1': customer
        }.get(id))
        calculator.get_objects_by_type = MagicMock(return_value=[project])
        analyzer.get_session = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))
        analyzer.get_object_by_id = MagicMock(return_value=project)
        analyzer.get_linked_objects = MagicMock(return_value=[])
        
        # Calculate priority
        priority_result = await calculator.calculate_project_priority('proj_1', save=False)
        assert priority_result.total_score > 70  # High priority due to tier_1 + deadline
        
        # Analyze scope change impact
        scope_result = await analyzer.analyze_scope_change_impact(
            project_id='proj_1',
            added_tasks=[{'title': 'Urgent Feature', 'estimated_hours': 40}],
            removed_tasks=[]
        )
        assert scope_result.impact_type == 'scope_change'
        assert len(scope_result.recommended_actions) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
