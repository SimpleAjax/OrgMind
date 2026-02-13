"""
Unit tests for worker health check server.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from orgmind.workers.health import create_health_app
from orgmind.workers.main import WorkerManager

@pytest.fixture
def mock_manager():
    manager = MagicMock(spec=WorkerManager)
    # Default to None for optional adapters
    manager.event_bus = None
    manager.neo4j_adapter = None
    manager.qdrant_store = None
    manager.meili_store = None
    return manager

def test_health_check_all_healthy(mock_manager):
    # Setup mocks
    mock_manager.event_bus = AsyncMock()
    mock_manager.event_bus.health_check.return_value = True
    
    mock_manager.neo4j_adapter = AsyncMock()
    mock_manager.neo4j_adapter.health_check.return_value = True
    
    mock_manager.qdrant_store = AsyncMock()
    mock_manager.qdrant_store.health_check.return_value = True
    
    mock_manager.meili_store = AsyncMock()
    mock_manager.meili_store.health_check.return_value = True
    
    app = create_health_app(mock_manager)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["checks"]["nats"] == "healthy"
    assert data["checks"]["neo4j"] == "healthy"
    assert data["checks"]["qdrant"] == "healthy"
    assert data["checks"]["meilisearch"] == "healthy"

def test_health_check_nats_unhealthy(mock_manager):
    mock_manager.event_bus = AsyncMock()
    mock_manager.event_bus.health_check.return_value = False
    
    app = create_health_app(mock_manager)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["nats"] == "unhealthy"

def test_health_check_missing_services(mock_manager):
    # Only event bus and Neo4j present
    mock_manager.event_bus = AsyncMock()
    mock_manager.event_bus.health_check.return_value = True
    
    mock_manager.neo4j_adapter = AsyncMock()
    mock_manager.neo4j_adapter.health_check.return_value = True
    
    # Qdrant and Meili are None (default in fixture)
    
    app = create_health_app(mock_manager)
    client = TestClient(app)
    
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "alive"
    assert data["checks"]["nats"] == "healthy"
    assert data["checks"]["neo4j"] == "healthy"
    assert "qdrant" not in data["checks"]
    assert "meilisearch" not in data["checks"]

def test_health_check_exception(mock_manager):
    mock_manager.event_bus = AsyncMock()
    mock_manager.event_bus.health_check.side_effect = Exception("Connection lost")
    
    app = create_health_app(mock_manager)
    client = TestClient(app)
    
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "degraded"
    assert "error: Connection lost" in data["checks"]["nats"]
