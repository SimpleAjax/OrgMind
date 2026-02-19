import pytest
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.storage.models import Base
from orgmind.storage.models_traces import DecisionTraceModel, ContextSuggestionModel
from orgmind.engine.digest_engine import DigestEngine
from orgmind.integrations.email.service import EmailService

# --- Setup ---

@pytest.fixture(scope="module")
def db_engine():
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

@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# --- Tests ---

def test_digest_integration(db_session):
    """
    Verify DigestEngine logic with real DB queries.
    """
    mock_email = MagicMock(spec=EmailService)
    engine = DigestEngine(mock_email)
    
    user_email = "test_user@example.com"
    now = datetime.utcnow()
    
    # 1. Create Data
    # - 1 success trace (missing context)
    t1 = DecisionTraceModel(
        id="t1", 
        action_type="Create", 
        timestamp=now, 
        user_id=user_email,
        input_payload={},
        status="success"
    )
    # - 1 success trace (has context)
    t2 = DecisionTraceModel(
        id="t2", 
        action_type="Delete", 
        timestamp=now, 
        user_id=user_email,
        input_payload={},
        status="success"
    )
    # - 1 active suggestion for t2
    s2 = ContextSuggestionModel(
        id="s2",
        trace_id="t2",
        suggestion_text="Reason",
        source="ai",
        status="accepted"
    )
    
    # - 1 old trace (ignored)
    t3 = DecisionTraceModel(
        id="t3", 
        action_type="Old", 
        timestamp=now - timedelta(days=10), 
        user_id=user_email,
        input_payload={}
    )
    
    db_session.add_all([t1, t2, s2, t3])
    db_session.commit()
    
    # 2. Run Engine
    engine.generate_and_send_digest(db_session, user_email)
    
    # 3. Verify
    mock_email.send_html_email.assert_called_once()
    args, _ = mock_email.send_html_email.call_args
    body = args[2]
    
    # Total traces in last week = 2 (t1, t2). t3 is too old.
    assert "<b>2</b>" in body
    
    # Missing traces = 1 (t1). t2 has accepted suggestion.
    assert "Decisions Missing Context: <b style=\"color: red;\">1</b>" in body
    assert "Create" in body
    assert "Delete" not in body # Should not list t2 as missing context
    assert "Old" not in body
