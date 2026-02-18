"""
Router for Object management endpoints.
"""

from typing import Annotated, Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from orgmind.api import schemas
from orgmind.api.dependencies import get_ontology_service, get_db
from orgmind.api.dependencies_auth import require_current_user, require_permission
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.models import ObjectModel
from orgmind.storage.models_access_control import UserModel
from orgmind.platform.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post("/", response_model=schemas.ObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_object(
    obj_create: schemas.ObjectCreate,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("object.create"))],
    tenant_id: UUID = Query(..., description="Tenant ID"),
):
    """
    Create a new Object.
    """
    import uuid
    new_id = str(uuid.uuid4())
    
    model = ObjectModel(
        id=new_id,
        type_id=str(obj_create.type_id),
        data=obj_create.data,
        created_by=obj_create.created_by
    )
    
    try:
        created = await service.create_object(
            session=session,
            entity=model,
            tenant_id=tenant_id,
            user_id=current_user.id
        )
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create object", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{object_id}", response_model=schemas.ObjectResponse)
async def get_object(
    object_id: UUID,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("object.read"))],
):
    """
    Get an Object by ID.
    """
    obj = service.get_object(session, str(object_id))
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj

@router.patch("/{object_id}", response_model=schemas.ObjectResponse)
async def update_object(
    object_id: UUID,
    updates: schemas.ObjectUpdate,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("object.update"))],
    tenant_id: UUID = Query(..., description="Tenant ID"),
):
    """
    Update an Object.
    """
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    try:
        updated = await service.update_object(
            session=session,
            object_id=str(object_id),
            updates=update_data,
            tenant_id=tenant_id,
            user_id=current_user.id
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Object not found")
        return updated
    except ValueError as e:
        # Schema validation error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update object", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(
    object_id: UUID,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("object.delete"))],
    tenant_id: UUID = Query(..., description="Tenant ID"),
):
    """
    Delete (soft delete) an Object.
    """
    success = await service.delete_object(
        session=session,
        object_id=str(object_id),
        tenant_id=tenant_id,
        user_id=current_user.id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Object not found")
    return None
@router.get("/", response_model=List[schemas.ObjectResponse])
def list_objects(
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_current_user)],
    _auth: Annotated[bool, Depends(require_permission("object.read"))],
    limit: int = 100,
    offset: int = 0,
):
    """
    List objects. 
    Results are filtered based on user permissions (RLS).
    """
    return service.list_objects(session, limit, offset, user=current_user)
