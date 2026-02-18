import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orgmind.storage.models import Base
from orgmind.triggers.models import RuleModel
from orgmind.triggers.repository import RuleRepository

@pytest.fixture
def session():
    # Use in-memory SQLite for isolated unit tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_rule_repository_crud(session):
    repo = RuleRepository()
    
    # 1. Create Rule
    rule = RuleModel(
        id="rule_001",
        name="Test Rule",
        description="A test rule",
        event_type_filter="object.created",
        condition={"==": [1, 1]},
        action_config={"type": "log"},
        enabled=True
    )
    repo.create(session, rule)
    
    # 2. Get Rule
    fetched = repo.get(session, "rule_001")
    assert fetched is not None
    assert fetched.name == "Test Rule"
    assert fetched.condition == {"==": [1, 1]}
    
    # 3. Update Rule
    repo.update(session, "rule_001", {"name": "Updated Rule", "enabled": False})
    updated = repo.get(session, "rule_001")
    assert updated.name == "Updated Rule"
    assert updated.enabled is False
    assert updated.version == 2
    
    # 4. List Rules
    rules = repo.list(session)
    assert len(rules) == 1
    
    # 5. Delete Rule
    deleted = repo.delete(session, "rule_001")
    assert deleted is True
    assert repo.get(session, "rule_001") is None

def test_list_by_event_type(session):
    repo = RuleRepository()
    
    r1 = RuleModel(
        id="r1", name="R1", event_type_filter="type.a", 
        condition={}, action_config={}, enabled=True
    )
    r2 = RuleModel(
        id="r2", name="R2", event_type_filter="type.b", 
        condition={}, action_config={}, enabled=True
    )
    r3 = RuleModel(
        id="r3", name="R3", event_type_filter="type.a", 
        condition={}, action_config={}, enabled=False
    )
    
    session.add_all([r1, r2, r3])
    session.commit()
    
    # Should only return enabled rules for type.a
    rules = repo.list_by_event_type(session, "type.a")
    assert len(rules) == 1
    assert rules[0].id == "r1"

def test_update_non_existent(session):
    repo = RuleRepository()
    result = repo.update(session, "fake_id", {"name": "New"})
    assert result is None

def test_delete_non_existent(session):
    repo = RuleRepository()
    result = repo.delete(session, "fake_id")
    assert result is False
