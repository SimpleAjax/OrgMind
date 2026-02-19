import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from temporalio.client import WorkflowExecutionStatus, WorkflowHandle, WorkflowExecutionDescription

from orgmind.api.main import app
from orgmind.api.dependencies import get_temporal_client

client = TestClient(app)

@pytest.fixture
def mock_temporal_client():
    mock_client = AsyncMock()
    return mock_client

@pytest.fixture
def override_dependency(mock_temporal_client):
    app.dependency_overrides[get_temporal_client] = lambda: mock_temporal_client
    yield
    app.dependency_overrides = {}

def test_start_workflow(mock_temporal_client, override_dependency):
    # Setup
    mock_handle = MagicMock(spec=WorkflowHandle)
    mock_handle.id = "test-workflow-id"
    mock_handle.run_id = "test-run-id"
    mock_temporal_client.start_workflow.return_value = mock_handle

    # Execute
    response = client.post("/api/v1/workflows/start", json={
        "workflow_name": "EmployeeOnboardingWorkflow",
        "args": ["Alice", "alice@example.com", "Engineering"],
        "workflow_id": "test-workflow-id"
    })

    # Verify
    assert response.status_code == 201
    assert response.json() == {"workflow_id": "test-workflow-id", "run_id": "test-run-id"}
    mock_temporal_client.start_workflow.assert_awaited_once()

def test_signal_workflow(mock_temporal_client, override_dependency):
    # Setup
    mock_handle = AsyncMock(spec=WorkflowHandle)
    # get_workflow_handle is SYNC, so it should be a MagicMock, not AsyncMock child
    mock_temporal_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    # Execute
    response = client.post("/api/v1/workflows/test-workflow-id/signal", json={
        "signal_name": "approve_onboarding",
        "args": []
    })

    # Verify
    assert response.status_code == 200
    assert response.json() == {"message": "Signal sent"}
    mock_temporal_client.get_workflow_handle.assert_called_with("test-workflow-id")
    mock_handle.signal.assert_awaited_with("approve_onboarding")

def test_cancel_workflow(mock_temporal_client, override_dependency):
    # Setup
    mock_handle = AsyncMock(spec=WorkflowHandle)
    mock_temporal_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    # Execute
    response = client.post("/api/v1/workflows/test-workflow-id/cancel")

    # Verify
    assert response.status_code == 200
    assert response.json() == {"message": "Cancellation requested"}
    mock_handle.cancel.assert_awaited_once()

def test_get_workflow_status(mock_temporal_client, override_dependency):
    # Setup
    mock_handle = AsyncMock(spec=WorkflowHandle)
    mock_desc = MagicMock(spec=WorkflowExecutionDescription)
    mock_desc.status = WorkflowExecutionStatus.RUNNING
    mock_desc.id = "test-workflow-id"
    mock_desc.run_id = "test-run-id"
    
    # describe is an async method on handle
    mock_handle.describe.return_value = mock_desc
    mock_temporal_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    # Execute
    response = client.get("/api/v1/workflows/test-workflow-id")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == "test-workflow-id"
    assert data["status"] == "RUNNING"
