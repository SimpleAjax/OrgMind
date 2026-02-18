from typing import Set, List
from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel

class RBACEngine:
    """
    Engine for Role-Based Access Control logic.
    Handles permission resolution from user roles.
    """
    
    def get_user_effective_permissions(self, user: UserModel) -> Set[str]:
        """
        Collect all permissions from all roles assigned to the user.
        Returns a set of permission names (e.g., {'object.read', 'object.write'}).
        """
        permissions = set()
        
        # Ensure roles are loaded (if not, we assume they are for now or use session)
        # With lazy="selectin" in models, they should be available if fetched via repo
        if not user.roles:
            return permissions
            
        for role in user.roles:
            if role.permissions:
                for perm in role.permissions:
                    permissions.add(perm.name)
        
        return permissions

    def has_permission(self, user: UserModel, required_permission: str) -> bool:
        """
        Check if user has a specific permission.
        """
        effective_permissions = self.get_user_effective_permissions(user)
        return required_permission in effective_permissions
    
    def has_any_permission(self, user: UserModel, required_permissions: List[str]) -> bool:
        """
        Check if user has at least one of the required permissions.
        """
        effective_permissions = self.get_user_effective_permissions(user)
        return not effective_permissions.isdisjoint(required_permissions)

    def has_all_permissions(self, user: UserModel, required_permissions: List[str]) -> bool:
        """
        Check if user has all of the required permissions.
        """
        effective_permissions = self.get_user_effective_permissions(user)
        return set(required_permissions).issubset(effective_permissions)
