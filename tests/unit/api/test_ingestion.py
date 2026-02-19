import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient

from orgmind.api.main import app
from orgmind.api.dependencies import get_event_publisher, get_ontology_service, get_db
from orgmind.events.publisher import EventPublisher
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.models import ObjectTypeModel

client = TestClient(app)

@pytest.fixture
def mock_publisher():
    mock = AsyncMock(spec=EventPublisher)
    return mock

@pytest.fixture
def mock_ontology_service():
    mock = MagicMock(spec=OntologyService)
    # create_object is async
    mock.create_object = AsyncMock()
    return mock

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def override_dependencies(mock_publisher, mock_ontology_service, mock_db):
    app.dependency_overrides[get_event_publisher] = lambda: mock_publisher
    app.dependency_overrides[get_ontology_service] = lambda: mock_ontology_service
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides = {}

def test_receive_webhook(mock_publisher, override_dependencies):
    response = client.post("/api/v1/ingestion/webhook/github", json={
        "source": "github",
        "event_type": "push",
        "payload": {"ref": "refs/heads/main"}
    })
    
    if response.status_code != 202:
        print(f"Error response: {response.json()}")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["message"] == "Event from github queued for processing."
    
    # Check if publish was awaited.
    # Note: EventPublisher.publish is async, so mocking it with AsyncMock means 
    # the mock object itself is awaitable? No, the method on the mock is awaitable.
    mock_publisher.publish.assert_awaited_once()
    event = mock_publisher.publish.call_args[0][0]
    assert event.event_type.value == "event.ingested"
    assert event.payload["source"] == "github"
    assert event.payload["original_type"] == "push"

def test_upload_csv(mock_ontology_service, override_dependencies):
    # Setup mock types
    mock_type = MagicMock(spec=ObjectTypeModel)
    mock_type.name = "Employee"
    mock_type.id = "type-uuid-123"
    
    # list_object_types is SYNC
    mock_ontology_service.list_object_types.return_value = [mock_type]
    
    # Create a CSV file
    csv_content = "name,email,department\nAlice,alice@example.com,Engineering\nBob,bob@example.com,Sales"
    file = io.BytesIO(csv_content.encode("utf-8"))
    
    response = client.post(
        "/api/v1/ingestion/upload-csv", 
        params={"object_type_name": "Employee"},
        files={"file": ("users.csv", file, "text/csv")}
    )
    
    if response.status_code != 201:
        print(f"Error response: {response.json()}")
    
    assert response.status_code == 201
    data = response.json()
    assert not data["errors"] # This will fail and show errors if any
    assert data["objects_created"] == 2
    assert data["status"] == "completed"
    
    # Verify calls
    assert mock_ontology_service.create_object.await_count == 2
    
def test_upload_csv_type_not_found(mock_ontology_service, override_dependencies):
    mock_ontology_service.list_object_types.return_value = []
    
    csv_content = "name,email\nAlice,alice@example.com"
    file = io.BytesIO(csv_content.encode("utf-8"))
    
    response = client.post(
        "/api/v1/ingestion/upload-csv", 
        params={"object_type_name": "Unknown"},
        files={"file": ("users.csv", file, "text/csv")}
    )
    
    if response.status_code != 404:
        print(f"Error response: {response.json()}")

    assert response.status_code == 404
