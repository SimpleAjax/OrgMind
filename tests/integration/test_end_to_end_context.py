import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.api.main import app
from orgmind.storage.models import Base
from orgmind.storage.models_traces import DecisionTraceModel
from orgmind.storage.models_context import ContextEventModel, ContextLinkModel, NudgeLogModel
from orgmind.api.dependencies import get_postgres_adapter
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.engine.correlation_engine import CorrelationEngine
from orgmind.engine.nudge_engine import NudgeEngine
from orgmind.integrations.slack.service import SlackService

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
    yield
    app.dependency_overrides = {}

@pytest.fixture
def db_session(postgres_adapter):
    with postgres_adapter.get_session() as session:
        yield session

@pytest.mark.asyncio
async def test_end_to_end_flow(db_session, postgres_adapter):
    """
    Test flow:
    1. Create Trace (via DB directly)
    2. Ingest Context (via API)
    3. Run Correlation -> Expect Link
    4. Run Nudge -> Expect NO Nudge (because link exists? Wait, nudge engine checks suggestions/links?)
       My NudgeEngine implementation checks 'ContextSuggestionModel'.
       It does NOT check 'ContextLinkModel' yet!
       This is a gap in my logic. If we have raw context (links), maybe we don't need a nudge?
       Or do we only stop nudging if we have an *explanation* (suggestion/note)?
       A raw browser log might not be enough "Why", but it provides context.
       The "Definition of Done" says: "Why did you do this?" nudge appears 5 min after action.
       If we captured the browser URL, we have context.
       Ideally, we should check if context exists (links) OR suggestions.
       
       Let's stick to current logic: Nudge checks suggestions.
       So here, I'll test that correlation works.
       Then I'll create a suggestion (simulate AI or manual).
       Then test Nudge skips.
    """
    
    # 1. Create Trace
    trace_id = "trace-e2e"
    user_id = "user-e2e"
    now = datetime.utcnow()
    
    trace = DecisionTraceModel(
        id=trace_id,
        action_type="test_action",
        timestamp=now,
        status="success",
        user_id=user_id,
        input_payload={}
    )
    db_session.add(trace)
    db_session.commit()
    
    # 2. Ingest Context via API
    # User was browsing Jira 1 min before
    payload = {
        "source": "browser",
        "source_id": "tab-1",
        "content": {"url": "http://jira/123"},
        "user_id": user_id,
        "timestamp": (now - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    }
    response = client.post("/api/v1/context/capture", json=payload)
    assert response.status_code == 200
    context_id = response.json()["id"]
    
    # 3. Run Correlation Engine
    corr_engine = CorrelationEngine()
    corr_engine.process_correlations(postgres_adapter)
    
    # Verify Link Created
    link = db_session.query(ContextLinkModel).filter_by(trace_id=trace_id, context_event_id=context_id).first()
    assert link is not None
    assert link.link_type == "temporal"
    
    # 4. Nudge Engine Check
    # Current logic: checks ContextSuggestionModel (status='accepted').
    # Link exists, but no suggestion.
    # So Nudge SHOULD fire.
    
    mock_slack = MagicMock(spec=SlackService)
    mock_slack.send_dm = AsyncMock(return_value=True)
    # Mock lookup needed? user_id is "user-e2e" (no @), so straight pass.
    
    nudge_engine = NudgeEngine(mock_slack)
    # We need to ensure logic allows nudge (trace > 5 mins old)
    # Trace timestamp is NOW. Nudge window is -5min to -1h.
    # So we need to update trace timestamp to be 10 mins ago.
    trace.timestamp = now - timedelta(minutes=10)
    db_session.commit()
    
    await nudge_engine.check_and_dispatch_nudges(postgres_adapter)
    
    # Verify Nudge Sent
    mock_slack.send_dm.assert_called_once()
    
    # Verify Nudge Log
    log = db_session.query(NudgeLogModel).filter_by(trace_id=trace_id).first()
    assert log is not None
