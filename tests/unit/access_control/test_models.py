import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from orgmind.storage.models import Base
from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel
from orgmind.storage.repositories.user_repository import UserRepository

# Setup in-memory SQLite for testing
@pytest.fixture(scope="module")
def engine():
    return create_engine("sqlite:///:memory:")

@pytest.fixture(scope="module")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()

def test_user_creation(session: Session):
    repo = UserRepository()
    user = UserModel(id="user1", email="test@example.com", name="Test User")
    created_user = repo.create_user(session, user)
    
    assert created_user.id == "user1"
    assert created_user.email == "test@example.com"
    
    fetched_user = repo.get_user(session, "user1")
    assert fetched_user is not None
    assert fetched_user.email == "test@example.com"

def test_role_creation(session: Session):
    repo = UserRepository()
    role = RoleModel(id="role1", name="Admin", description="Admin Role")
    created_role = repo.create_role(session, role)
    
    assert created_role.id == "role1"
    assert created_role.name == "Admin"

def test_user_role_assignment(session: Session):
    repo = UserRepository()
    
    user = UserModel(id="user2", email="user2@example.com", name="User 2")
    role = RoleModel(id="role2", name="Editor", description="Editor Role")
    
    repo.create_user(session, user)
    repo.create_role(session, role)
    
    # Assign role
    user.roles.append(role)
    session.add(user)
    session.flush()
    
    # Verify assignment
    fetched_user = repo.get_user(session, "user2")
    assert len(fetched_user.roles) == 1
    assert fetched_user.roles[0].name == "Editor"

def test_permission_creation_and_assignment(session: Session):
    repo = UserRepository()
    
    perm = PermissionModel(id="perm1", name="object.read", description="Read objects")
    role = RoleModel(id="role3", name="Viewer", description="Viewer Role")
    
    repo.create_permission(session, perm)
    repo.create_role(session, role)
    
    # Assign permission to role
    role.permissions.append(perm)
    session.add(role)
    session.flush()
    
    # Verify
    fetched_role = repo.get_role(session, "role3")
    assert len(fetched_role.permissions) == 1
    assert fetched_role.permissions[0].name == "object.read"
