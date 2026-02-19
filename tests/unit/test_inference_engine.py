import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from orgmind.storage.models_traces import DecisionTraceModel, ContextSnapshotModel, InferenceRuleModel
from orgmind.engine.inference_engine import InferenceEngine, FieldChangeSignal, TemporalSignal, GraphSignal

class MockPostgresAdapter:
    def get_session(self):
        return MagicMock()

@pytest.fixture
def engine():
    return InferenceEngine(MockPostgresAdapter())

def test_field_change_signal():
    signal = FieldChangeSignal()
    trace = DecisionTraceModel(input_payload={"priority": "high", "status": "open"})
    
    # Match value
    assert signal.evaluate(trace, None, {"field": "priority", "value": "high"}) is True
    # Mismatch value
    assert signal.evaluate(trace, None, {"field": "priority", "value": "low"}) is False
    # Missing field
    assert signal.evaluate(trace, None, {"field": "category", "value": "bug"}) is False
    # Field exists (any value)
    assert signal.evaluate(trace, None, {"field": "status"}) is True

def test_temporal_signal():
    signal = TemporalSignal()
    
    # Friday
    friday = datetime(2023, 10, 27, 12, 0, 0) # Oct 27 2023 is a Friday
    trace_fri = DecisionTraceModel(timestamp=friday, status="success")
    assert signal.evaluate(trace_fri, None, {"condition": "is_friday"}) is True
    assert signal.evaluate(trace_fri, None, {"condition": "is_weekend"}) is False # Friday is not weekend by default python weekday
    
    # Saturday
    saturday = datetime(2023, 10, 28, 12, 0, 0)
    trace_sat = DecisionTraceModel(timestamp=saturday)
    assert signal.evaluate(trace_sat, None, {"condition": "is_weekend"}) is True
    
    # Failed
    trace_fail = DecisionTraceModel(status="failure", timestamp=friday)
    assert signal.evaluate(trace_fail, None, {"condition": "is_failed"}) is True

def test_graph_signal():
    signal = GraphSignal()
    
    snapshot = ContextSnapshotModel(
        graph_neighborhood={
            "nodes": [{"id": "1", "type": "Task"}],
            "relationships": [
                {"type": "BLOCKS", "start": "1", "end": "2"},
                {"type": "ASSIGNED_TO", "start": "1", "end": "3"}
            ]
        }
    )
    trace = DecisionTraceModel()
    
    assert signal.evaluate(trace, snapshot, {"relationship": "BLOCKS"}) is True
    assert signal.evaluate(trace, snapshot, {"relationship": "DEPENDS_ON"}) is False
    
    # Empty snapshot
    assert signal.evaluate(trace, None, {"relationship": "BLOCKS"}) is False

def test_inference_engine_evaluation():
    # Setup mocks
    mock_postgres = MagicMock()
    mock_session = MagicMock()
    mock_postgres.get_session.return_value.__enter__.return_value = mock_session
    
    engine = InferenceEngine(mock_postgres)
    
    # Data
    trace_id = str(uuid.uuid4())
    trace = DecisionTraceModel(id=trace_id, input_payload={"priority": "high"}, timestamp=datetime.now())
    rule = InferenceRuleModel(
        id="rule1", 
        name="High Priority", 
        condition_logic={"type": "field_change", "config": {"field": "priority", "value": "high"}},
        is_active=True,
        description="Priority set to high"
    )
    
    mock_session.query.return_value.filter_by.return_value.first.return_value = trace
    mock_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [rule]
    
    # Run
    suggestion_ids = engine.evaluate_trace(trace_id)
    
    # Assert
    assert len(suggestion_ids) == 1
    mock_session.add.assert_called_once()
    added_suggestion = mock_session.add.call_args[0][0]
    assert added_suggestion.trace_id == trace_id
    assert "High Priority" in added_suggestion.suggestion_text
