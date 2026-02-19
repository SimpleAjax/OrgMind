import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.api.main import app
from orgmind.storage.models import Base
from orgmind.storage.models_context import ContextEventModel, ContextSourceType
from orgmind.api.dependencies import get_postgres_adapter
from orgmind.storage.postgres_adapter import PostgresAdapter

client = TestClient(app)

# --- Test DB Setup ---

@pytest.fixture(scope="module")
def db_engine():
    """Use SQLite for integration tests."""
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    # Ensure all models are registered
    import orgmind.storage.models
    import orgmind.storage.models_traces
    import orgmind.storage.models_context
    
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture(scope="module")
def postgres_adapter(db_engine):
    """Mock PostgresAdapter."""
    mock_adapter = MagicMock(spec=PostgresAdapter)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    
    from contextlib import contextmanager
    @contextmanager
    def get_session():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            
    mock_adapter.get_session = get_session
    return mock_adapter

@pytest.fixture(autouse=True)
def override_dependencies(postgres_adapter):
    app.dependency_overrides[get_postgres_adapter] = lambda: postgres_adapter
    yield
    app.dependency_overrides = {}

@pytest.fixture
def db_session(postgres_adapter):
    with postgres_adapter.get_session() as session:
        yield session

# --- Tests ---

def test_capture_context_api(db_session):
    """
    Test capturing a single context event via API.
    """
    payload = {
        "source": "browser",
        "source_id": "tab-123",
        "content": {"url": "https://jira.com/task-1", "title": "Fix Bug"},
        "user_id": "user-1",
        "session_id": "session-1"
    }
    
    response = client.post("/api/v1/context/capture", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["source"] == "browser"
    assert data["source_id"] == "tab-123"
    assert data["content"]["url"] == "https://jira.com/task-1"
    
    # Verify DB
    event = db_session.query(ContextEventModel).filter_by(id=data["id"]).first()
    assert event is not None
    assert event.source == "browser"

def test_batch_capture_context(db_session):
    """
    Test batch capture.
    """
    payloads = [
        {
            "source": "slack",
            "source_id": "msg-1",
            "content": {"text": "Hello"},
            "user_id": "user-1"
        },
        {
            "source": "slack",
            "source_id": "msg-2",
            "content": {"text": "World"},
            "user_id": "user-2"
        }
    ]
    
    response = client.post("/api/v1/context/batch", json=payloads)
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2
    assert data[0]["source"] == "slack"
    assert data[1]["content"]["text"] == "World"
    
    # Verify DB count
    count = db_session.query(ContextEventModel).filter(ContextEventModel.source == "slack").count()
    assert count >= 2

def test_get_recent_context(db_session):
    """
    Test retrieving recent context.
    """
    # Create some historical data
    e1 = ContextEventModel(
        id="hist-1", source="ide", source_id="file-1", content={}, 
        timestamp=datetime.utcnow() - timedelta(minutes=10)
    )
    e2 = ContextEventModel(
        id="hist-2", source="ide", source_id="file-2", content={}, 
        timestamp=datetime.utcnow() - timedelta(minutes=5)
    )
    db_session.add(e1)
    db_session.add(e2)
    db_session.commit()
    
    response = client.get("/api/v1/context/recent?limit=10&source=ide")
    assert response.status_code == 200
    data = response.json()
    
    # Should be sorted desc by timestamp
    assert len(data) >= 2
    assert data[0]["id"] == "hist-2" # Newer
    assert data[1]["id"] == "hist-1" # Older
