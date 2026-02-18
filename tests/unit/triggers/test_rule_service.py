from unittest.mock import Mock, MagicMock
from orgmind.triggers.service import RuleService
from orgmind.triggers import schemas
from orgmind.triggers.models import RuleModel

def test_create_rule():
    mock_repo = Mock()
    service = RuleService(mock_repo)
    mock_session = Mock()
    
    rule_create = schemas.RuleCreate(
        name="Test Rule",
        description="A test rule",
        event_type_filter="object.created",
        condition={"==": [1, 1]},
        action_config={"type": "log"},
        enabled=True
    )
    
    # Mock return
    mock_repo.create.return_value = RuleModel(id="uuid-123", name="Test Rule")
    
    result = service.create_rule(mock_session, rule_create, "user-123")
    
    assert result.id == "uuid-123"
    assert result.name == "Test Rule"
    
    # Verify repo called correctly
    mock_repo.create.assert_called_once()
    created_arg = mock_repo.create.call_args[0][1]
    assert created_arg.name == "Test Rule"
    assert created_arg.created_by == "user-123"
    assert created_arg.enabled is True

def test_get_rule():
    mock_repo = Mock()
    service = RuleService(mock_repo)
    mock_session = Mock()
    
    mock_repo.get.return_value = RuleModel(id="1", name="R1")
    
    result = service.get_rule(mock_session, "1")
    assert result.name == "R1"
    mock_repo.get.assert_called_with(mock_session, "1")

def test_update_rule():
    mock_repo = Mock()
    service = RuleService(mock_repo)
    mock_session = Mock()
    
    update_data = schemas.RuleUpdate(name="New Name")
    mock_repo.update.return_value = RuleModel(id="1", name="New Name")
    
    result = service.update_rule(mock_session, "1", update_data)
    assert result.name == "New Name"
    mock_repo.update.assert_called_with(mock_session, "1", {"name": "New Name"})

def test_update_rule_empty():
    mock_repo = Mock()
    service = RuleService(mock_repo)
    mock_session = Mock()
    
    # Empty update should just fetch
    mock_repo.get.return_value = RuleModel(id="1")
    
    service.update_rule(mock_session, "1", schemas.RuleUpdate())
    
    mock_repo.update.assert_not_called()
    mock_repo.get.assert_called_with(mock_session, "1")

def test_delete_rule():
    mock_repo = Mock()
    service = RuleService(mock_repo)
    mock_session = Mock()
    
    mock_repo.delete.return_value = True
    
    assert service.delete_rule(mock_session, "1") is True
    mock_repo.delete.assert_called_with(mock_session, "1")
