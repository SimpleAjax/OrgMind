import pytest
from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel
from orgmind.access_control.rbac import RBACEngine

@pytest.fixture
def permissions():
    return {
        "read": PermissionModel(id="read", name="object.read"),
        "write": PermissionModel(id="write", name="object.write"),
        "delete": PermissionModel(id="delete", name="object.delete"),
    }

@pytest.fixture
def roles(permissions):
    # Viewer: read only
    viewer = RoleModel(id="viewer", name="Viewer")
    viewer.permissions = [permissions["read"]]
    
    # Editor: read, write
    editor = RoleModel(id="editor", name="Editor")
    editor.permissions = [permissions["read"], permissions["write"]]
    
    # Admin: all
    admin = RoleModel(id="admin", name="Admin")
    admin.permissions = [permissions["read"], permissions["write"], permissions["delete"]]
    
    return {"viewer": viewer, "editor": editor, "admin": admin}

def test_user_permissions_resolution(roles):
    engine = RBACEngine()
    
    # User with Viewer role
    user1 = UserModel(id="u1", email="u1@test.com", roles=[roles["viewer"]])
    perms1 = engine.get_user_effective_permissions(user1)
    
    assert "object.read" in perms1
    assert "object.write" not in perms1
    assert engine.has_permission(user1, "object.read")
    assert not engine.has_permission(user1, "object.write")

    # User with Editor role
    user2 = UserModel(id="u2", email="u2@test.com", roles=[roles["editor"]])
    perms2 = engine.get_user_effective_permissions(user2)
    
    assert "object.read" in perms2
    assert "object.write" in perms2
    assert "object.delete" not in perms2

def test_multiple_roles(roles):
    engine = RBACEngine()
    
    # User with Viewer AND specific delete role (if we had one, but let's mix viewer and a custom role)
    custom_role = RoleModel(id="deleter", name="Deleter")
    # Permissions are mocked so we can reuse objects if needed but better create new one or reference
    # Here just create a permission on the fly
    perm_custom = PermissionModel(id="custom", name="custom.perm")
    custom_role.permissions = [perm_custom]
    
    user3 = UserModel(id="u3", email="u3@test.com", roles=[roles["viewer"], custom_role])
    perms3 = engine.get_user_effective_permissions(user3)
    
    assert "object.read" in perms3
    assert "custom.perm" in perms3
    assert len(perms3) == 2

def test_has_any_permission(roles):
    engine = RBACEngine()
    user = UserModel(id="u4", roles=[roles["editor"]])
    
    # Has read and write. 
    # Check for read OR delete -> True because has read
    assert engine.has_any_permission(user, ["object.read", "object.delete"])
    
    # Check for delete OR specific -> False because has neither
    assert not engine.has_any_permission(user, ["object.delete", "admin.access"])

def test_has_all_permissions(roles):
    engine = RBACEngine()
    user = UserModel(id="u5", roles=[roles["editor"]])
    
    # Has read and write
    assert engine.has_all_permissions(user, ["object.read", "object.write"])
    
    # Missing delete
    assert not engine.has_all_permissions(user, ["object.read", "object.delete"])
