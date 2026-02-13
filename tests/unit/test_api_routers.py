"""
Unit tests for API Routers using mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime
from fastapi.testclient import TestClient
from orgmind.api.main import app
from orgmind.api.dependencies import get_ontology_service, get_db
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.models import ObjectTypeModel, ObjectModel

# Mock Dependencies
mock_service = AsyncMock(spec=OntologyService)
mock_session = MagicMock()

def override_get_ontology_service():
    return mock_service

def override_get_db():
    yield mock_session

app.dependency_overrides[get_ontology_service] = override_get_ontology_service
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_mocks():
    mock_service.reset_mock()
    mock_session.reset_mock()


class TestObjectTypeRouter:
    """Tests for /api/v1/types/objects"""

    def test_create_object_type(self):
        """Test creating an object type via API."""
        tenant_id = str(uuid4())
        payload = {
            "name": "Project",
            "description": "A project entity",
            "properties": {"deadline": {"type": "date"}},
            "implements": []
        }
        
        # Setup Mock Return
        mock_return = ObjectTypeModel(
            id=str(uuid4()),
            name=payload["name"],
            description=payload["description"],
            properties=payload["properties"],
            implements=payload["implements"],
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            sensitive_properties=[]
        )
        mock_service.create_object_type.return_value = mock_return
        
        # Execute Request
        v1_url = f"/api/v1/types/objects?tenant_id={tenant_id}"
        response = client.post(v1_url, json=payload)
        
        # Verify Response
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["id"] == mock_return.id
        
        # Verify Service Call
        mock_service.create_object_type.assert_called_once()
        call_args = mock_service.create_object_type.call_args[1]
        assert call_args["tenant_id"] == UUID(tenant_id)
        assert call_args["schema"].name == "Project"

    def test_get_object_type(self):
        """Test getting an object type."""
        type_id = str(uuid4())
        mock_return = ObjectTypeModel(
            id=type_id,
            name="Task",
            properties={},
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            implements=[],
            sensitive_properties=[]
        )
        mock_service.get_object_type.return_value = mock_return
        
        response = client.get(f"/api/v1/types/objects/{type_id}")
        
        assert response.status_code == 200
        assert response.json()["id"] == type_id
        assert response.json()["name"] == "Task"


class TestObjectRouter:
    """Tests for /api/v1/objects"""

    def test_create_object(self):
        """Test creating an object instance."""
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        type_id = str(uuid4())
        
        payload = {
            "type_id": type_id,
            "data": {"title": "My Project"},
            "created_by": user_id
        }
        
        obj_id = str(uuid4())
        mock_return = ObjectModel(
            id=obj_id,
            type_id=type_id,
            data=payload["data"],
            created_by=user_id,
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_service.create_object.return_value = mock_return
        
        response = client.post(
            f"/api/v1/objects/?tenant_id={tenant_id}&user_id={user_id}",
            json=payload
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == obj_id
        assert data["type_id"] == type_id
        
        # Verify Service Call
        mock_service.create_object.assert_called_once()
        call_args = mock_service.create_object.call_args[1]
        assert str(call_args["tenant_id"]) == tenant_id
        assert call_args["entity"].data == payload["data"]

    def test_create_object_validation_error(self):
        """Test object creation failure (e.g. invalid schema)."""
        tenant_id = str(uuid4())
        # Simulate service raising ValueError
        mock_service.create_object.side_effect = ValueError("Invalid property 'title'")
        
        payload = {
            "type_id": str(uuid4()),
            "data": {"invalid": "data"},
            "created_by": str(uuid4())
        }
        
        response = client.post(
            f"/api/v1/objects/?tenant_id={tenant_id}",
            json=payload
        )
        
        assert response.status_code == 400
        assert "Invalid property" in response.json()["detail"]

    def test_update_object(self):
        """Test updating an object."""
        tenant_id = str(uuid4())
        obj_id = str(uuid4())
        
        payload = {
            "data": {"title": "Updated Title"}
        }
        
        mock_return = ObjectModel(
            id=obj_id,
            type_id=str(uuid4()),
            data={"title": "Updated Title"},
            status="active",
            version=2,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_service.update_object.return_value = mock_return
        
        response = client.patch(
            f"/api/v1/objects/{obj_id}?tenant_id={tenant_id}",
            json=payload
        )
        
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "Updated Title"

    def test_delete_object(self):
        """Test deleting an object."""
        tenant_id = str(uuid4())
        obj_id = str(uuid4())
        
        mock_service.delete_object.return_value = True
        
        response = client.delete(f"/api/v1/objects/{obj_id}?tenant_id={tenant_id}")
        
        assert response.status_code == 204
        mock_service.delete_object.assert_called_once()
