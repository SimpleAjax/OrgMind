import pytest
from unittest.mock import Mock, MagicMock
from orgmind.engine.context_capture import ContextSnapshotService
from orgmind.storage.models_traces import ContextSnapshotModel

@pytest.fixture
def mock_postgres():
    adapter = Mock()
    session = Mock()
    # Use MagicMock for context manager to support __enter__
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = None
    adapter.get_session.return_value = cm
    return adapter

@pytest.fixture
def mock_neo4j():
    adapter = Mock()
    return adapter

@pytest.fixture
def service(mock_postgres, mock_neo4j):
    return ContextSnapshotService(mock_postgres, mock_neo4j)

def test_capture_snapshot_success(service, mock_postgres, mock_neo4j):
    # Setup
    entity_ids = ["e1", "e2"]
    
    # Mock Neo4j Graph Result with objects mostly, but for nodes dicts are fine if code handles it?
    # Code: nodes = [dict(n) for n in record.get("nodes", [])]
    # So nodes need to be convertible to dict.
    
    # Mock Rel object
    mock_rel = MagicMock()
    mock_rel.id = "r1"
    mock_rel.element_id = "r1"
    mock_rel.type = "LINKS_TO"
    mock_rel.start_node.element_id = "n1"
    mock_rel.end_node.element_id = "n2"
    # Make it iterable for dict() conversion
    mock_rel.__iter__.return_value = iter([("prop", "val")])
    
    mock_neo4j.execute_read.return_value = [{
        "nodes": [{"id": "n1", "labels": ["Object"]}],
        "rels": [mock_rel]
    }]
    
    # Mock Postgres Entity Result (query objects)
    session = mock_postgres.get_session.return_value.__enter__.return_value
    mock_obj1 = Mock()
    mock_obj1.id = "e1"
    mock_obj1.type_id = "t1" 
    mock_obj1.data = {}
    mock_obj1.status = "active"
    mock_obj1.version = 1
    
    # Configure query return
    session.query.return_value.filter.return_value.all.return_value = [mock_obj1]
    
    # Act
    snapshot_id = service.capture_snapshot(entity_ids)
    
    # Assert
    assert snapshot_id is not None
    # Check Neo4j called
    mock_neo4j.execute_read.assert_called_once()
    # Check Postgres saved
    session.add.assert_called_once()
    saved_snapshot = session.add.call_args[0][0]
    assert isinstance(saved_snapshot, ContextSnapshotModel)
    assert saved_snapshot.id == snapshot_id
    assert "e1" in saved_snapshot.entity_states
    assert len(saved_snapshot.graph_neighborhood["nodes"]) == 1

def test_capture_snapshot_empty_entities(service, mock_postgres, mock_neo4j):
    snapshot_id = service.capture_snapshot([])
    
    # Should create empty snapshot or handle?
    # Current implementation logs empty dicts.
    
    session = mock_postgres.get_session.return_value.__enter__.return_value
    session.add.assert_called_once()
    saved_snapshot = session.add.call_args[0][0]
    assert saved_snapshot.entity_states == {}
    assert saved_snapshot.graph_neighborhood == {'nodes': [], 'relationships': []}

def test_capture_snapshot_neo4j_failure(service, mock_postgres, mock_neo4j):
    # Ensure Entity fetch succeeds (empty list is fine)
    session = mock_postgres.get_session.return_value.__enter__.return_value
    session.query.return_value.filter.return_value.all.return_value = []
    
    mock_neo4j.execute_read.side_effect = Exception("Neo4j Down")
    
    # Should not raise, but log error and save snapshot with error info
    snapshot_id = service.capture_snapshot(["e1"])
    
    assert snapshot_id is not None
    session.add.assert_called_once()
    saved_snapshot = session.add.call_args[0][0]
    assert "error" in saved_snapshot.graph_neighborhood
    assert saved_snapshot.graph_neighborhood["error"] == "Neo4j Down"
