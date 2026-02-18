import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orgmind.api.main import app
from orgmind.storage.models import Base, ObjectTypeModel, ObjectModel
from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel
from orgmind.storage.models_audit import AuditLogModel
from orgmind.api.dependencies import get_db, get_event_bus

# Use in-memory SQLite
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
    app.dependency_overrides[get_event_bus] = MockEventBus
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
    # Permissions
    p_read = PermissionModel(id="p_read", name="object.read", description="Read objects")
    p_create = PermissionModel(id="p_create", name="object.create", description="Create objects")
    
    # Roles
    r_admin = RoleModel(id="r_admin", name="Admin", permissions=[p_read, p_create])
    r_user = RoleModel(id="r_user", name="User", permissions=[p_read, p_create])
    
    # Users
    u_admin = UserModel(id="admin_user", email="admin@test.com", roles=[r_admin])
    u_user = UserModel(id="normal_user", email="user@test.com", roles=[r_user])
    
    # Object Type
    t_note = ObjectTypeModel(
        id=str(uuid4()), 
        name="Note", 
        properties={"content": {"type": "string"}}
    )
    
    db_session.add_all([p_read, p_create, r_admin, r_user, u_admin, u_user, t_note])
    db_session.commit()
    
    # Create Objects directly to simulate state
    # Object A created by Admin
    obj_a = ObjectModel(
        id=str(uuid4()),
        type_id=t_note.id,
        data={"content": "Admin Note"},
        created_by=u_admin.id
    )
    
    # Object B created by User
    obj_b = ObjectModel(
        id=str(uuid4()),
        type_id=t_note.id,
        data={"content": "User Note"},
        created_by=u_user.id
    )
    
    db_session.add_all([obj_a, obj_b])
    db_session.commit()
    
    return {
        "admin": u_admin,
        "user": u_user,
        "obj_a": obj_a,
        "obj_b": obj_b
    }

def test_visibility_filtering(client, test_data, db_session):
    admin_id = test_data["admin"].id
    user_id = test_data["user"].id
    obj_a_id = test_data["obj_a"].id
    obj_b_id = test_data["obj_b"].id
    
    # 1. Normal User calls List
    resp = client.get("/api/v1/objects/", headers={"X-User-ID": user_id})
    assert resp.status_code == 200
    data = resp.json()
    
    # Expect only 1 object (User Note)
    assert len(data) == 1
    assert data[0]["id"] == obj_b_id
    assert data[0]["data"]["content"] == "User Note"
    
    # 2. Admin calls List
    resp = client.get("/api/v1/objects/", headers={"X-User-ID": admin_id})
    assert resp.status_code == 200
    data = resp.json()
    
    # Expect 2 objects
    assert len(data) == 2
    ids = [o["id"] for o in data]
    assert obj_a_id in ids
    assert obj_b_id in ids
