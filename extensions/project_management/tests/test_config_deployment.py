"""
Tests for verifying the PM configuration deployment.

Run with: pytest extensions/project_management/tests/test_config_deployment.py -v
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

# OrgMind imports
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.storage.models import ObjectTypeModel, LinkTypeModel, ObjectModel, LinkModel
from orgmind.platform.config import settings


@pytest.fixture(scope="module")
def postgres():
    """Database connection fixture."""
    pg = PostgresAdapter(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )
    yield pg


class TestObjectTypes:
    """Test that all Object Types are properly configured."""
    
    def test_customer_object_type_exists(self, postgres):
        """Verify ot_customer type exists with correct properties."""
        with postgres.get_session() as session:
            ot = session.query(ObjectTypeModel).filter_by(id="ot_customer").first()
            assert ot is not None, "ot_customer not found"
            assert ot.name == "Customer"
            assert "tier" in ot.properties
            assert ot.properties["tier"]["type"] == "string"
            assert "tier_1" in ot.properties["tier"]["enum"]
    
    def test_project_object_type_exists(self, postgres):
        """Verify ot_project type exists with AI fields."""
        with postgres.get_session() as session:
            ot = session.query(ObjectTypeModel).filter_by(id="ot_project").first()
            assert ot is not None, "ot_project not found"
            assert "priority_score" in ot.properties
            assert "risk_score" in ot.properties
            assert ot.properties["priority_score"]["type"] == "number"
    
    def test_task_object_type_has_ai_fields(self, postgres):
        """Verify ot_task has AI prediction fields."""
        with postgres.get_session() as session:
            ot = session.query(ObjectTypeModel).filter_by(id="ot_task").first()
            assert ot is not None, "ot_task not found"
            assert "predicted_delay_probability" in ot.properties
            assert ot.properties["predicted_delay_probability"]["type"] == "number"
            assert "predicted_completion_date" in ot.properties
    
    def test_person_object_type_exists(self, postgres):
        """Verify ot_person type exists."""
        with postgres.get_session() as session:
            ot = session.query(ObjectTypeModel).filter_by(id="ot_person").first()
            assert ot is not None, "ot_person not found"
            assert "working_hours_per_day" in ot.properties
            assert "default_availability_percent" in ot.properties
    
    def test_nudge_object_type_exists(self, postgres):
        """Verify ot_nudge type exists for AI notifications."""
        with postgres.get_session() as session:
            ot = session.query(ObjectTypeModel).filter_by(id="ot_nudge").first()
            assert ot is not None, "ot_nudge not found"
            assert "type" in ot.properties
            assert "severity" in ot.properties
            assert "ai_confidence" in ot.properties
    
    def test_all_object_types_exist(self, postgres):
        """Verify all expected object types exist."""
        expected = [
            "ot_customer", "ot_contact_info", "ot_project", "ot_sprint",
            "ot_sprint_task", "ot_task", "ot_task_skill_requirement",
            "ot_person", "ot_skill", "ot_person_skill", "ot_assignment",
            "ot_leave_period", "ot_productivity_profile", "ot_nudge", "ot_nudge_action"
        ]
        
        with postgres.get_session() as session:
            existing = {ot.id for ot in session.query(ObjectTypeModel).all()}
            
            for obj_type in expected:
                assert obj_type in existing, f"Missing object type: {obj_type}"


class TestLinkTypes:
    """Test that all Link Types are properly configured."""
    
    def test_customer_project_link_exists(self, postgres):
        """Verify lt_customer_has_project link type."""
        with postgres.get_session() as session:
            lt = session.query(LinkTypeModel).filter_by(id="lt_customer_has_project").first()
            assert lt is not None
            assert lt.source_type == "ot_customer"
            assert lt.target_type == "ot_project"
            assert lt.cardinality == "one_to_many"
    
    def test_task_assignment_link_exists(self, postgres):
        """Verify lt_task_assigned_to link type."""
        with postgres.get_session() as session:
            lt = session.query(LinkTypeModel).filter_by(id="lt_task_assigned_to").first()
            assert lt is not None
            assert lt.source_type == "ot_task"
            assert lt.target_type == "ot_assignment"
    
    def test_task_dependency_link_exists(self, postgres):
        """Verify lt_task_blocks link type with properties."""
        with postgres.get_session() as session:
            lt = session.query(LinkTypeModel).filter_by(id="lt_task_blocks").first()
            assert lt is not None
            assert lt.source_type == "ot_task"
            assert lt.target_type == "ot_task"  # Self-referencing
            assert "dependency_type" in lt.properties
            assert "lag_days" in lt.properties
    
    def test_person_skill_link_exists(self, postgres):
        """Verify lt_person_has_skill link type."""
        with postgres.get_session() as session:
            lt = session.query(LinkTypeModel).filter_by(id="lt_person_has_skill").first()
            assert lt is not None
            assert lt.source_type == "ot_person"
            assert lt.target_type == "ot_person_skill"


class TestDataOperations:
    """Test CRUD operations on configured types."""
    
    def test_create_customer(self, postgres):
        """Test creating a customer object."""
        with postgres.get_session() as session:
            customer = ObjectModel(
                id=f"test_cust_{uuid4().hex[:8]}",
                type_id="ot_customer",
                data={
                    "name": "Test Customer Inc",
                    "tier": "tier_1",
                    "contract_value": 100000,
                    "sla_level": "premium",
                    "status": "active"
                }
            )
            session.add(customer)
            session.commit()
            
            # Verify
            found = session.query(ObjectModel).filter_by(id=customer.id).first()
            assert found is not None
            assert found.data["name"] == "Test Customer Inc"
            assert found.data["tier"] == "tier_1"
    
    def test_create_project_with_relationships(self, postgres):
        """Test creating project with customer relationship."""
        with postgres.get_session() as session:
            # Create customer
            customer_id = f"test_cust_{uuid4().hex[:8]}"
            customer = ObjectModel(
                id=customer_id,
                type_id="ot_customer",
                data={"name": "Customer", "tier": "tier_2", "status": "active"}
            )
            
            # Create project
            project_id = f"test_proj_{uuid4().hex[:8]}"
            project = ObjectModel(
                id=project_id,
                type_id="ot_project",
                data={
                    "name": "Test Project",
                    "status": "planning",
                    "planned_start": datetime.now().isoformat(),
                    "planned_end": (datetime.now() + timedelta(days=30)).isoformat(),
                    "priority_score": 75.5,
                    "risk_score": 25.0
                }
            )
            
            # Create link
            link = LinkModel(
                id=f"test_link_{uuid4().hex[:8]}",
                type_id="lt_customer_has_project",
                source_id=customer_id,
                target_id=project_id,
                data={}
            )
            
            session.add_all([customer, project, link])
            session.commit()
            
            # Verify
            found_link = session.query(LinkModel).filter_by(id=link.id).first()
            assert found_link is not None
            assert found_link.source_id == customer_id
            assert found_link.target_id == project_id
    
    def test_create_task_with_skills(self, postgres):
        """Test creating task with skill requirements."""
        with postgres.get_session() as session:
            # Create skill
            skill_id = f"test_skill_{uuid4().hex[:8]}"
            skill = ObjectModel(
                id=skill_id,
                type_id="ot_skill",
                data={"name": "Python", "category": "technical"}
            )
            
            # Create task
            task_id = f"test_task_{uuid4().hex[:8]}"
            task = ObjectModel(
                id=task_id,
                type_id="ot_task",
                data={
                    "title": "Implement API",
                    "estimated_hours": 16,
                    "priority": "high",
                    "status": "backlog",
                    "predicted_delay_probability": 0.15
                }
            )
            
            # Create skill requirement
            req_id = f"test_req_{uuid4().hex[:8]}"
            requirement = ObjectModel(
                id=req_id,
                type_id="ot_task_skill_requirement",
                data={
                    "task_id": task_id,
                    "skill_id": skill_id,
                    "minimum_proficiency": 3,
                    "is_mandatory": True
                }
            )
            
            session.add_all([skill, task, requirement])
            session.commit()
            
            # Verify
            found_req = session.query(ObjectModel).filter_by(id=req_id).first()
            assert found_req is not None
            assert found_req.data["minimum_proficiency"] == 3
    
    def test_create_assignment(self, postgres):
        """Test creating person-task assignment."""
        with postgres.get_session() as session:
            # Create person
            person_id = f"test_person_{uuid4().hex[:8]}"
            person = ObjectModel(
                id=person_id,
                type_id="ot_person",
                data={
                    "name": "John Doe",
                    "email": "john@example.com",
                    "role": "developer",
                    "default_availability_percent": 100
                }
            )
            
            # Create task
            task_id = f"test_task_{uuid4().hex[:8]}"
            task = ObjectModel(
                id=task_id,
                type_id="ot_task",
                data={
                    "title": "Test Task",
                    "estimated_hours": 8,
                    "status": "todo"
                }
            )
            
            # Create assignment
            assignment_id = f"test_assign_{uuid4().hex[:8]}"
            assignment = ObjectModel(
                id=assignment_id,
                type_id="ot_assignment",
                data={
                    "person_id": person_id,
                    "task_id": task_id,
                    "allocation_percent": 50,
                    "planned_hours": 4,
                    "planned_start": datetime.now().isoformat(),
                    "planned_end": (datetime.now() + timedelta(days=2)).isoformat(),
                    "status": "planned"
                }
            )
            
            session.add_all([person, task, assignment])
            session.commit()
            
            # Verify
            found = session.query(ObjectModel).filter_by(id=assignment_id).first()
            assert found is not None
            assert found.data["allocation_percent"] == 50


class TestComplexScenarios:
    """Test complex business scenarios."""
    
    def test_project_with_multiple_tasks(self, postgres):
        """Test project with multiple tasks and dependencies."""
        with postgres.get_session() as session:
            # Create project
            project_id = f"test_proj_{uuid4().hex[:8]}"
            project = ObjectModel(
                id=project_id,
                type_id="ot_project",
                data={"name": "Multi-task Project", "status": "active"}
            )
            
            # Create tasks
            task1_id = f"test_task1_{uuid4().hex[:8]}"
            task1 = ObjectModel(
                id=task1_id,
                type_id="ot_task",
                data={"title": "Task 1", "status": "done"}
            )
            
            task2_id = f"test_task2_{uuid4().hex[:8]}"
            task2 = ObjectModel(
                id=task2_id,
                type_id="ot_task",
                data={"title": "Task 2", "status": "in_progress"}
            )
            
            # Create dependency: task1 blocks task2
            link = LinkModel(
                id=f"test_dep_{uuid4().hex[:8]}",
                type_id="lt_task_blocks",
                source_id=task1_id,
                target_id=task2_id,
                data={"dependency_type": "hard", "lag_days": 0}
            )
            
            # Link tasks to project
            link1 = LinkModel(
                id=f"test_link1_{uuid4().hex[:8]}",
                type_id="lt_project_has_task",
                source_id=project_id,
                target_id=task1_id,
                data={}
            )
            link2 = LinkModel(
                id=f"test_link2_{uuid4().hex[:8]}",
                type_id="lt_project_has_task",
                source_id=project_id,
                target_id=task2_id,
                data={}
            )
            
            session.add_all([project, task1, task2, link, link1, link2])
            session.commit()
            
            # Verify structure
            links = session.query(LinkModel).filter(
                LinkModel.type_id == "lt_project_has_task",
                LinkModel.source_id == project_id
            ).all()
            assert len(links) == 2
    
    def test_sprint_with_tasks(self, postgres):
        """Test sprint containing tasks from multiple projects."""
        with postgres.get_session() as session:
            # Create sprint
            sprint_id = f"test_sprint_{uuid4().hex[:8]}"
            sprint = ObjectModel(
                id=sprint_id,
                type_id="ot_sprint",
                data={
                    "name": "Sprint 1",
                    "start_date": datetime.now().isoformat(),
                    "end_date": (datetime.now() + timedelta(days=14)).isoformat(),
                    "status": "active"
                }
            )
            
            # Create task
            task_id = f"test_task_{uuid4().hex[:8]}"
            task = ObjectModel(
                id=task_id,
                type_id="ot_task",
                data={"title": "Sprint Task", "status": "todo"}
            )
            
            # Create sprint-task association
            sprint_task = ObjectModel(
                id=f"test_st_{uuid4().hex[:8]}",
                type_id="ot_sprint_task",
                data={
                    "sprint_id": sprint_id,
                    "task_id": task_id,
                    "status": "todo"
                }
            )
            
            session.add_all([sprint, task, sprint_task])
            session.commit()
            
            # Verify
            found = session.query(ObjectModel).filter_by(type_id="ot_sprint_task").first()
            assert found is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
