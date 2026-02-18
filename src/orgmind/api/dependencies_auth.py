from typing import Annotated, Optional, Callable
from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session

from orgmind.api.database import get_db
from orgmind.storage.repositories.user_repository import UserRepository
from orgmind.storage.repositories.audit_repository import AuditRepository
from orgmind.storage.models_access_control import UserModel, PermissionModel
from orgmind.access_control.rbac import RBACEngine
from orgmind.access_control.abac import ABACEngine

# Helper for current implementation (Header based Auth)
API_KEY_HEADER = "X-User-ID"

def get_user_repository() -> UserRepository:
    return UserRepository()

def get_audit_repository() -> AuditRepository:
    return AuditRepository()

def get_rbac_engine() -> RBACEngine:
    return RBACEngine()

def get_abac_engine() -> ABACEngine:
    return ABACEngine()

def get_current_user(
    x_user_id: Annotated[Optional[str], Header(alias=API_KEY_HEADER)] = None,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
) -> UserModel:
    """
    Dependency to retrieve the current user based on X-User-ID header.
    In production, this would parse a JWT token.
    """
    if not x_user_id:
        return None
        
    user = user_repo.get_user(db, x_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid User ID"
        )
    return user

def require_current_user(
    user: Annotated[UserModel, Depends(get_current_user)]
) -> UserModel:
    """Enforce that a user is authenticated."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

class PermissionChecker:
    """
    Callable dependency to check for a specific permission.
    """
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(
        self, 
        request: Request,
        user: Annotated[UserModel, Depends(require_current_user)],
        rbac: Annotated[RBACEngine, Depends(get_rbac_engine)],
        audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
        db: Annotated[Session, Depends(get_db)]
    ) -> bool:
        has_perm = rbac.has_permission(user, self.required_permission)
        
        # Audit Log
        decision = "allow" if has_perm else "deny"
        resource_path = request.url.path
        method = request.method
        
        audit_repo.create_log(
            session=db,
            user_id=user.id,
            action=self.required_permission,
            resource=f"{method}:{resource_path}",
            decision=decision,
            reason=f"RBAC check for {self.required_permission}",
            metadata={"ip": request.client.host if request.client else None}
        )
        # Ensure log is persisted immediately
        db.commit()
        
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {self.required_permission}"
            )
        return True

def require_permission(permission_name: str) -> Callable:
    """Factory for permission dependency."""
    return PermissionChecker(permission_name)
