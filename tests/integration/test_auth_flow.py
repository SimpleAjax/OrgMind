import pytest
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

# Mock Event Bus to avoid NATS dependency in this specific Auth test
# We only care about Auth middleware here, not event publication
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
    print(f"DEBUG: Tables in Base.metadata: {list(Base.metadata.tables.keys())}")
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
    # Create Permissions
    p_create = PermissionModel(id="p1", name="object.create", description="Create objects")
    p_read = PermissionModel(id="p2", name="object.read", description="Read objects")
    
    # Create Roles
    r_admin = RoleModel(id="admin_role", name="Admin", permissions=[p_create, p_read])
    r_viewer = RoleModel(id="viewer_role", name="Viewer", permissions=[p_read])
    r_guest = RoleModel(id="guest_role", name="Guest", permissions=[])
    
    # Create Users
    u_admin = UserModel(id="admin_user", email="admin@test.com", roles=[r_admin])
    u_viewer = UserModel(id="viewer_user", email="viewer@test.com", roles=[r_viewer])
    u_guest = UserModel(id="guest_user", email="guest@test.com", roles=[r_guest])
    
    db_session.add_all([p_create, p_read, r_admin, r_viewer, r_guest, u_admin, u_viewer, u_guest])
    
    # Create a Type for object creation
    # Use valid UUID for type_id to match Pydantic schema
    task_type_id = str(uuid4())
    t_task = ObjectTypeModel(
        id=task_type_id, 
        name="Task", 
        properties={"title": {"type": "string"}}
    )
    db_session.add(t_task)
    
    db_session.commit()
    
    return {
        "admin": u_admin,
        "viewer": u_viewer,
        "guest": u_guest,
        "type_id": task_type_id
    }

def test_auth_endpoints(client, test_data):
    admin_id = test_data["admin"].id
    viewer_id = test_data["viewer"].id
    guest_id = test_data["guest"].id
    type_id = test_data["type_id"]
    tenant_id = str(uuid4())
    
    # 1. POST /objects (Requires object.create)
    
    payload = {
        "type_id": type_id,
        "data": {"title": "Test Task"},
        "created_by": "test_script"
    }
    
    # Case A: No Auth -> 401
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload)
    assert resp.status_code == 401
    
    # Case B: Guest (No User) if invalid ID -> 401
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload, headers={"X-User-ID": "invalid"})
    assert resp.status_code == 401
    
    # Case C: Guest (Valid User, No Perms) -> 403
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload, headers={"X-User-ID": guest_id})
    assert resp.status_code == 403
    
    # Case D: Viewer (Read Perm, No Create) -> 403
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload, headers={"X-User-ID": viewer_id})
    assert resp.status_code == 403
    
    # Case E: Admin (Create Perm) -> 201
    resp = client.post(f"/api/v1/objects/?tenant_id={tenant_id}", json=payload, headers={"X-User-ID": admin_id})
    if resp.status_code != 201:
        print(f"\nResponse Body: {resp.json()}\n")
    assert resp.status_code == 201
    created_obj = resp.json()
    obj_id = created_obj["id"]
    
    # 2. GET /objects/{id} (Requires object.read)
    
    # Case A: Viewer -> 200
    resp = client.get(f"/api/v1/objects/{obj_id}", headers={"X-User-ID": viewer_id})
    assert resp.status_code == 200
    assert resp.json()["id"] == obj_id
    
    # Case B: Guest -> 403
    resp = client.get(f"/api/v1/objects/{obj_id}", headers={"X-User-ID": guest_id})
    assert resp.status_code == 403
