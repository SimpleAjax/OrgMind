import pytest
from unittest.mock import Mock, MagicMock, ANY
from orgmind.engine.decision_tracer import DecisionTraceService
from orgmind.storage.models_traces import DecisionTraceModel

@pytest.fixture
def mock_postgres():
    adapter = Mock()
    session = Mock()
    # Use MagicMock for context manager
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = None
    adapter.get_session.return_value = cm
    return adapter

@pytest.fixture
def mock_snapshot_service():
    return Mock()

@pytest.fixture
def service(mock_postgres, mock_snapshot_service):
    return DecisionTraceService(mock_postgres, mock_snapshot_service)

def test_log_decision_success(service, mock_postgres):
    trace_id = service.log_decision(
        action_type="test_action",
        input_payload={"k": "v"},
        rule_id="rule-1",
        latency_ms=10.5
    )
    
    assert trace_id is not None
    
    session = mock_postgres.get_session.return_value.__enter__.return_value
    session.add.assert_called_once()
    saved_trace = session.add.call_args[0][0]
    
    assert isinstance(saved_trace, DecisionTraceModel)
    assert saved_trace.id == trace_id
    assert saved_trace.action_type == "test_action"
    assert saved_trace.latency_ms == 10.5
    assert saved_trace.snapshot_id is None

def test_log_decision_with_snapshot(service, mock_postgres, mock_snapshot_service):
    mock_snapshot_service.capture_snapshot.return_value = "snap-123"
    
    trace_id = service.log_decision(
        action_type="test_action",
        input_payload={},
        involved_entity_ids=["e1"]
    )
    
    mock_snapshot_service.capture_snapshot.assert_called_with(["e1"])
    
    session = mock_postgres.get_session.return_value.__enter__.return_value
    saved_trace = session.add.call_args[0][0]
    assert saved_trace.snapshot_id == "snap-123"

def test_log_decision_snapshot_failure_logs_anyway(service, mock_postgres, mock_snapshot_service):
    # If snapshot fails, trace should still be logged
    mock_snapshot_service.capture_snapshot.side_effect = Exception("Snapshot Failed")
    
    trace_id = service.log_decision(
        action_type="test_action",
        input_payload={},
        involved_entity_ids=["e1"]
    )
    
    assert trace_id is not None
    # Check trace saved without snapshot_id
    session = mock_postgres.get_session.return_value.__enter__.return_value
    saved_trace = session.add.call_args[0][0]
    assert saved_trace.snapshot_id is None

def test_log_decision_db_failure_raises(service, mock_postgres):
    session = mock_postgres.get_session.return_value.__enter__.return_value
    session.add.side_effect = Exception("DB Error")
    
    # Should raise exception
    with pytest.raises(Exception, match="DB Error"):
        service.log_decision("action", {})
