import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from orgmind.storage.models import Base
from orgmind.storage.repositories.audit_repository import AuditRepository
from orgmind.storage.models_audit import AuditLogModel

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_audit_log(db_session):
    repo = AuditRepository()
    
    log = repo.create_log(
        session=db_session,
        user_id="test_user",
        action="test.action",
        resource="test:resource",
        decision="allow",
        reason="testing",
        metadata={"ip": "127.0.0.1"}
    )
    
    assert log.id is not None
    assert log.decision == "allow"
    assert log.metadata_context["ip"] == "127.0.0.1"

def test_list_audit_logs(db_session):
    repo = AuditRepository()
    # clean table first or assume empty in test DB
    # or just create new ones and check count/ordering
    
    log1 = repo.create_log(db_session, "u1", "act", "res", "allow")
    log2 = repo.create_log(db_session, "u2", "act", "res", "deny")
    
    logs = repo.list(db_session)
    # verify ordering (descending timestamp)
    # ids might not be ordered, but we can check if both are present
    ids = [l.id for l in logs]
    assert log1.id in ids
    assert log2.id in ids
