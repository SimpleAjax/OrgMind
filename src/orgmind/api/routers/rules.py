from typing import List, Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from orgmind.triggers import schemas
from orgmind.triggers.service import RuleService
from orgmind.triggers.repository import RuleRepository
from orgmind.api.dependencies import get_db
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.storage.models_access_control import UserModel


router = APIRouter()

def get_rule_service() -> RuleService:
    repository = RuleRepository()
    return RuleService(repository)

@router.post("/", response_model=schemas.RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    rule_create: schemas.RuleCreate,
    service: Annotated[RuleService, Depends(get_rule_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("rule.create"))],
):
    """
    Create a new automation rule.
    """
    try:
        # Use current_user.id as created_by
        return service.create_rule(session, rule_create, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[schemas.RuleResponse])
def list_rules(
    service: Annotated[RuleService, Depends(get_rule_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("rule.read"))],
    limit: int = 100,
    offset: int = 0,
):
    """
    List all rules.
    """
    return service.list_rules(session, limit, offset)

@router.get("/{rule_id}", response_model=schemas.RuleResponse)
def get_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("rule.read"))],
):
    """
    Get a rule by ID.
    """
    rule = service.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@router.patch("/{rule_id}", response_model=schemas.RuleResponse)
def update_rule(
    rule_id: str,
    rule_update: schemas.RuleUpdate,
    service: Annotated[RuleService, Depends(get_rule_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("rule.update"))],
):
    """
    Update a rule.
    """
    rule = service.update_rule(session, rule_id, rule_update)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("rule.delete"))],
):
    """
    Delete a rule.
    """
    if not service.delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return None
