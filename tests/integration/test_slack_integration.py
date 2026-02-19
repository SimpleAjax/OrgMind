import pytest
import time
import hmac
import hashlib
import json
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
from orgmind.platform.config import settings

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
    # Override settings for testing signature
    settings.SLACK_SIGNING_SECRET = "test-secret"
    yield
    app.dependency_overrides = {}
    settings.SLACK_SIGNING_SECRET = ""

@pytest.fixture
def db_session(postgres_adapter):
    with postgres_adapter.get_session() as session:
        yield session

# --- Helpers ---

def generate_signature(timestamp: str, body: str, secret: str) -> str:
    base = f"v0:{timestamp}:{body}".encode('utf-8')
    sig = hmac.new(secret.encode('utf-8'), base, hashlib.sha256).hexdigest()
    return f"v0={sig}"

# --- Tests ---

def test_slack_url_verification():
    """Test standard Slack URL verification handshake."""
    timestamp = str(int(time.time()))
    payload = {"type": "url_verification", "challenge": "test-challenge-123", "token": "foo"}
    body = json.dumps(payload)
    sig = generate_signature(timestamp, body, "test-secret")
    
    response = client.post(
        "/api/v1/integrations/slack/events", 
        content=body,
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"challenge": "test-challenge-123"}

def test_slack_message_event(db_session):
    """Test receiving a message event."""
    timestamp = str(int(time.time()))
    msg_ts = str(time.time())
    payload = {
        "token": "foo",
        "team_id": "T123",
        "api_app_id": "A123",
        "event": {
            "type": "message",
            "channel": "C123",
            "user": "U123",
            "text": "Hello World",
            "ts": msg_ts
        },
        "type": "event_callback",
        "event_id": "Ev123",
        "event_time": int(time.time())
    }
    body = json.dumps(payload)
    sig = generate_signature(timestamp, body, "test-secret")
    
    response = client.post(
        "/api/v1/integrations/slack/events", 
        content=body,
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    
    # Verify in DB
    # Background tasks might run sync in TestClient? Yes, usually.
    
    # We need to wait a moment if it's async, but fastAPI background tasks run after response.
    # TestClient in sync mode usually executes them.
    
    event = db_session.query(ContextEventModel).filter(ContextEventModel.source == "slack").first()
    assert event is not None
    assert event.source_id == f"C123_{msg_ts}"
    assert event.content["text"] == "Hello World"
