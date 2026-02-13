"""
Router for Object Type management endpoints.
"""

from typing import List, Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from orgmind.api import schemas
from orgmind.api.dependencies import get_ontology_service, get_db
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.models import ObjectTypeModel
from orgmind.platform.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post("/objects", response_model=schemas.ObjectTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_object_type(
    obj_type: schemas.ObjectTypeCreate,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    tenant_id: UUID = Query(..., description="Tenant ID"),  # TODO: Extract from auth token
    user_id: Optional[UUID] = Query(None, description="User ID"),
):
    """
    Create a new Object Type.
    """
    logger.info("Creating object type", name=obj_type.name, tenant_id=str(tenant_id))
    
    # Map Schema to Model
    # Note: Using UUID() for IDs is standard, but models use str. Converting.
    import uuid
    new_id = str(uuid.uuid4())
    
    model = ObjectTypeModel(
        id=new_id,
        name=obj_type.name,
        description=obj_type.description,
        properties=obj_type.properties,
        implements=obj_type.implements,
        sensitive_properties=obj_type.sensitive_properties,
        default_permissions=obj_type.default_permissions,
    )
    
    try:
        created = await service.create_object_type(
            session=session,
            schema=model,
            tenant_id=tenant_id,
            user_id=user_id
        )
        return created
    except Exception as e:
        logger.error("Failed to create object type", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/objects/{type_id}", response_model=schemas.ObjectTypeResponse)
async def get_object_type(
    type_id: UUID,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
):
    """
    Get an Object Type by ID.
    """
    obj_type = service.get_object_type(session, str(type_id))
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    return obj_type

@router.put("/objects/{type_id}", response_model=schemas.ObjectTypeResponse)
async def update_object_type(
    type_id: UUID,
    updates: schemas.ObjectTypeUpdate,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    tenant_id: UUID = Query(..., description="Tenant ID"),
    user_id: Optional[UUID] = Query(None, description="User ID"),
):
    """
    Update an Object Type.
    """
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated = await service.update_object_type(
        session=session,
        type_id=str(type_id),
        updates=update_data,
        tenant_id=tenant_id,
        user_id=user_id
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Object Type not found")
    return updated

@router.delete("/objects/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object_type(
    type_id: UUID,
    service: Annotated[OntologyService, Depends(get_ontology_service)],
    session: Annotated[Session, Depends(get_db)],
    tenant_id: UUID = Query(..., description="Tenant ID"),
    user_id: Optional[UUID] = Query(None, description="User ID"),
):
    """
    Delete an Object Type.
    """
    success = await service.delete_object_type(
        session=session,
        type_id=str(type_id),
        tenant_id=tenant_id,
        user_id=user_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Object Type not found")
    return None
