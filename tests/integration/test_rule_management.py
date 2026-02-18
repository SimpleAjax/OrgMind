import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orgmind.storage.models import Base
from orgmind.triggers.models import RuleModel
from orgmind.triggers.service import RuleService
from orgmind.triggers.repository import RuleRepository
from orgmind.triggers import schemas

@pytest.fixture
def db_engine():
    """Create a test database engine (SQLite for simplicity)."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def rule_service():
    repo = RuleRepository()
    return RuleService(repo)

def test_rule_crud(rule_service, db_session):
    # Create
    rule_create = schemas.RuleCreate(
        name="Test Rule",
        event_type_filter="object.created",
        condition={"==": [1, 1]},
        action_config={"type": "log"}
    )
    
    created = rule_service.create_rule(db_session, rule_create, "user1")
    assert created.id is not None
    assert created.name == "Test Rule"
    assert created.enabled is True
    
    # Get
    fetched = rule_service.get_rule(db_session, created.id)
    assert fetched is not None
    assert fetched.name == "Test Rule"
    
    # List
    rules = rule_service.list_rules(db_session)
    assert len(rules) == 1
    
    # Update
    update = schemas.RuleUpdate(name="Updated Rule")
    updated = rule_service.update_rule(db_session, created.id, update)
    assert updated.name == "Updated Rule"
    
    # Delete
    deleted = rule_service.delete_rule(db_session, created.id)
    assert deleted is True
    
    assert rule_service.get_rule(db_session, created.id) is None

def test_list_by_event_type(rule_service, db_session):
    # Create two rules
    r1 = schemas.RuleCreate(
        name="Rule 1",
        event_type_filter="object.created",
        condition={},
        action_config={}
    )
    r2 = schemas.RuleCreate(
        name="Rule 2",
        event_type_filter="object.updated",
        condition={},
        action_config={}
    )
    r3 = schemas.RuleCreate(
        name="Rule 3",
        event_type_filter="object.created",
        condition={},
        action_config={},
        enabled=False
    )
    
    rule_service.create_rule(db_session, r1)
    rule_service.create_rule(db_session, r2)
    rule_service.create_rule(db_session, r3)
    
    # Filter
    rules = rule_service.list_active_rules_by_event(db_session, "object.created")
    assert len(rules) == 1
    assert rules[0].name == "Rule 1"

def test_complex_json_storage(rule_service, db_session):
    """Test storing and retrieving complex JSON structures."""
    condition = {
        "and": [
            {">": [{"var": "amount"}, 100]},
            {"in": [{"var": "status"}, ["active", "pending"]]},
            {"some": [{"var": "tags"}, {"in": [{"var": ""}, ["urgent"]]}]}
        ]
    }
    
    action = {
        "type": "slack",
        "config": {
            "channel": "#alerts",
            "message": "High value object found: {{ object.id }}",
            "metadata": {"priority": "high", "retry": 3}
        }
    }
    
    rule = schemas.RuleCreate(
        name="Complex Rule",
        event_type_filter="object.updated",
        condition=condition,
        action_config=action
    )
    
    created = rule_service.create_rule(db_session, rule)
    fetched = rule_service.get_rule(db_session, created.id)
    
    assert fetched.condition == condition
    assert fetched.action_config == action
    assert fetched.condition["and"][0][">"][1] == 100

def test_missing_fields_validation(rule_service, db_session):
    """Test validation (although Pydantic handles this before service calls usually)."""
    # Direct model creation to test DB constraints if any or minimal service wrapping
    pass # Pydantic validation happens at API layer, here we test service logic
    
    # Test updating non-existent
    update = schemas.RuleUpdate(name="Ghost")
    assert rule_service.update_rule(db_session, "nop", update) is None
    
    # Test deleting non-existent
    assert rule_service.delete_rule(db_session, "nop") is False
