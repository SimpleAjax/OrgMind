from typing import List, Optional, Type
from sqlalchemy.orm import Session
from sqlalchemy import select

from orgmind.storage.models_access_control import UserModel, RoleModel, PermissionModel
from .base import BaseRepository

class UserRepository(BaseRepository[UserModel]):
    
    # --- BaseRepository Implementation (Users) ---
    def create(self, session: Session, entity: UserModel) -> UserModel:
        session.add(entity)
        session.flush()
        return entity

    def get(self, session: Session, id: str) -> Optional[UserModel]:
        return session.get(UserModel, id)

    def update(self, session: Session, id: str, updates: dict) -> Optional[UserModel]:
        user = self.get(session, id)
        if not user:
            return None
        
        for key, value in updates.items():
            setattr(user, key, value)
            
        session.flush()
        return user

    def delete(self, session: Session, id: str) -> bool:
        user = self.get(session, id)
        if not user:
            return False
        session.delete(user)
        session.flush()
        return True

    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[UserModel]:
        stmt = select(UserModel).limit(limit).offset(offset)
        return list(session.scalars(stmt).all())

    # --- Role & Permission Specifics ---
    
    # Alias for clarity if needed, but 'create' works for users
    def create_user(self, session: Session, user: UserModel) -> UserModel:
        return self.create(session, user)

    def get_user(self, session: Session, user_id: str) -> Optional[UserModel]:
        return self.get(session, user_id)

    def get_user_by_email(self, session: Session, email: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(UserModel.email == email)
        return session.scalars(stmt).first()

    # The update/delete specific methods can be handled by generic ones or wrappers if needed.


    # --- Roles ---
    def create_role(self, session: Session, role: RoleModel) -> RoleModel:
        session.add(role)
        session.flush()
        return role

    def get_role(self, session: Session, role_id: str) -> Optional[RoleModel]:
        return session.get(RoleModel, role_id)
    
    def get_role_by_name(self, session: Session, name: str) -> Optional[RoleModel]:
        stmt = select(RoleModel).where(RoleModel.name == name)
        return session.scalars(stmt).first()

    # --- Permissions ---
    def create_permission(self, session: Session, permission: PermissionModel) -> PermissionModel:
        session.add(permission)
        session.flush()
        return permission
    
    def get_permission(self, session: Session, permission_id: str) -> Optional[PermissionModel]:
        return session.get(PermissionModel, permission_id)
        
    def get_permission_by_name(self, session: Session, name: str) -> Optional[PermissionModel]:
        stmt = select(PermissionModel).where(PermissionModel.name == name)
        return session.scalars(stmt).first()
