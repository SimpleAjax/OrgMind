import pytest
import time
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.api.main import app
from orgmind.storage.models import Base, ObjectTypeModel
from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel
from orgmind.storage.models_audit import AuditLogModel
from orgmind.api.dependencies import get_db, get_event_bus
from orgmind.api.dependencies_auth import get_user_repository

# Use in-memory SQLite for speed and isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.pool import StaticPool
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

class MockEventBus:
    async def publish(self, *args, **kwargs):
        pass
    async def connect(self):
        pass
    async def disconnect(self):
        pass

from orgmind.api.dependencies_auth import get_rbac_engine, get_audit_repository
from orgmind.access_control.rbac import RBACEngine
from orgmind.storage.repositories.audit_repository import AuditRepository

class RealAuditRepository(AuditRepository):
    pass

def override_get_event_bus():
    return MockEventBus()

def override_get_rbac_engine():
    return RBACEngine()

def override_get_audit_repository():
    return AuditRepository()

# Capture original overrides to restore them
original_dependency_overrides = {}

@pytest.fixture(scope="module", autouse=True)
def setup_teardown_module():
    global original_dependency_overrides
    original_dependency_overrides = app.dependency_overrides.copy()
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    app.dependency_overrides[get_rbac_engine] = override_get_rbac_engine
    app.dependency_overrides[get_audit_repository] = override_get_audit_repository
    
    yield
    
    app.dependency_overrides = original_dependency_overrides 

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_db):
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_data(db_session):
    # Setup User & Permissions
    p_read = PermissionModel(id="p_read_obj", name="object.read", description="Read objects")
    r_viewer = RoleModel(id="viewer_role", name="Viewer", permissions=[p_read])
    u_viewer = UserModel(id="viewer_user", email="viewer@test.com", roles=[r_viewer])
    
    # Setup Object Type and Object
    t_task = ObjectTypeModel(id=str(uuid4()), name="Task", properties={})
    
    db_session.add_all([p_read, r_viewer, u_viewer, t_task])
    
    # We need an object to read
    # But for 'create' test we need create permission. 
    # Let's test Access Deny on 'create' endpoint for viewer.
    
    db_session.commit()
    
    return {
        "viewer": u_viewer,
        "type_id": t_task.id
    }

def test_audit_log_generation(client, test_data, db_session):
    viewer_id = test_data["viewer"].id
    type_id = test_data["type_id"]
    tenant_id = str(uuid4())
    
    # 1. Attempt Create (Should Fail - 403)
    payload = {
        "type_id": type_id,
        "data": {"title": "Test Task"},
        "created_by": "test_script"
    }
    
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload, headers={"X-User-ID": viewer_id})
    assert resp.status_code == 403
    
    # Verify Audit Log
    # Need new session to see committed data? 
    # TestClient runs in same process but might use different session if not careful.
    # We are using static pool sqlite so data persists.
    
    # Retrieve logs
    logs = db_session.query(AuditLogModel).all()
    # We expect at least one log
    assert len(logs) > 0
    last_log = logs[-1]
    
    assert last_log.user_id == viewer_id
    assert last_log.action == "object.create"
    assert last_log.decision == "deny"
    
    # 2. Attempt Read (Should Succeed - Assuming we had an object, but let's test a GET even if 404)
    # We don't have object id.
    # Let's use a random ID. 
    random_obj_id = str(uuid4())
    resp = client.get(f"/api/v1/objects/{random_obj_id}", headers={"X-User-ID": viewer_id})
    # Should get 404 Not Found (from Logic) OR 403 depending on order.
    # Code:
    # @router.get("/{object_id}")
    # async def get_object(..., _auth: ... require_permission("object.read"))
    # Auth check happens first.
    # So we expect 404 (because we have permission, so auth passes, then service returns None).
    
    assert resp.status_code == 404
    
    # Verify Audit Log for Allow
    logs_after = db_session.query(AuditLogModel).all()
    assert len(logs_after) > len(logs)
    last_log = logs_after[-1]
    
    assert last_log.user_id == viewer_id
    assert last_log.action == "object.read"
    assert last_log.decision == "allow"
