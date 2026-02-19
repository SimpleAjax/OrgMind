import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.storage.models import Base
from orgmind.evolution.models import (
    OutcomeDefinitionModel, ScheduledOutcomeModel, OutcomeEventModel, 
    ScheduledOutcomeStatus
)
from orgmind.evolution.scheduler import OutcomeScheduler

# --- Fixtures ---

@pytest.fixture
def db_engine():
    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine)

@pytest.fixture
def mock_adapter(db_session_factory):
    adapter = MagicMock()
    # verify that get_session works as a context manager
    # We need to wrap the session in a context manager
    
    class SessionContext:
        def __init__(self):
            self.session = db_session_factory()
        def __enter__(self):
            return self.session
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()

    adapter.get_session.side_effect = SessionContext
    return adapter

@pytest.fixture
def scheduler(mock_adapter):
    return OutcomeScheduler(mock_adapter)

# --- Tests ---

@pytest.mark.asyncio
async def test_scheduler_flow(scheduler, db_session_factory):
    # 1. Setup Data
    session = db_session_factory()
    
    # Create Outcome Definition
    definition = OutcomeDefinitionModel(
        id="def-1",
        name="Test Outcome",
        collector_type="mock",
        parameters={"mock_response": {"success": True}, "score_type": "boolean"}
    )
    session.add(definition)
    session.commit()
    session.close() # Ensure committed
    
    # 2. Schedule Check
    trace_id = "trace-123"
    scheduled_id = await scheduler.schedule_check(
        trace_id=trace_id,
        definition_id="def-1",
        delay_minutes=-10 # Schedule in the past so it runs immediately
    )
    
    # Verify in DB
    session = db_session_factory()
    scheduled = session.get(ScheduledOutcomeModel, scheduled_id)
    assert scheduled is not None
    assert scheduled.status == ScheduledOutcomeStatus.PENDING
    assert scheduled.trace_id == trace_id
    session.close()
    
    # 3. Run Due Checks
    await scheduler.run_due_checks()
    
    # 4. Verify Results
    session = db_session_factory()
    scheduled = session.get(ScheduledOutcomeModel, scheduled_id)
    assert scheduled.status == ScheduledOutcomeStatus.COMPLETED
    assert scheduled.attempts == 1
    
    # Check Outcome Event
    assert len(scheduled.events) == 1
    event = scheduled.events[0]
    assert event.score == 1.0
    assert event.metrics["success"] is True
    
    session.close()

@pytest.mark.asyncio
async def test_scheduler_failure_handling(scheduler, db_session_factory):
    # Test with unknown collector type
    session = db_session_factory()
    definition = OutcomeDefinitionModel(
        id="def-bad",
        name="Bad Definition",
        collector_type="unknown_collector",
        parameters={}
    )
    session.add(definition)
    session.commit()
    session.close()
    
    scheduled_id = await scheduler.schedule_check(
        trace_id="trace-bad",
        definition_id="def-bad",
        delay_minutes=-1
    )
    
    await scheduler.run_due_checks()
    
    session = db_session_factory()
    scheduled = session.get(ScheduledOutcomeModel, scheduled_id)
    assert scheduled.status == ScheduledOutcomeStatus.FAILED
    assert "Unknown collector type" in scheduled.last_error
    session.close()

@pytest.mark.asyncio
async def test_pattern_detection(scheduler, db_session_factory):
    # Setup data with some history
    session = db_session_factory()
    definition = OutcomeDefinitionModel(
        id="def-pattern",
        name="Pattern Test",
        collector_type="mock",
        parameters={}
    )
    
    # Create a completed scheduled outcome + event
    scheduled = ScheduledOutcomeModel(
        id="sched-1",
        definition_id="def-pattern",
        trace_id="trace-1",
        scheduled_at=datetime.utcnow(),
        status=ScheduledOutcomeStatus.COMPLETED
    )
    
    event = OutcomeEventModel(
        id="evt-1",
        scheduled_outcome=scheduled,
        metrics={},
        score=0.8
    )
    
    session.add(definition)
    session.add(scheduled)
    session.add(event)
    session.commit()
    session.close()
    
    # Test Detector
    # Use a real/mock adapter for PatternDetector
    from orgmind.evolution.patterns import PatternDetector
    
    # We need an adapter that can create sessions. Our mock_adapter fixture does this.
    # But wait, mock_adapter is a Mock object. PatternDetector uses `with self.db.get_session() as session:`.
    # Our fixture ensures this works.
    mock_adapter = scheduler.db
    detector = PatternDetector(mock_adapter)
    
    stats = await detector.analyze_definition("def-pattern")
    
    assert stats["definition_id"] == "def-pattern"
    assert stats["total_events"] == 1
    assert stats["average_score"] == 0.8
