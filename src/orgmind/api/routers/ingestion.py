import csv
import io
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from orgmind.api.dependencies import get_event_publisher, get_ontology_service, get_db
from orgmind.events.ingestion.schemas import IngestionResponse, WebhookPayload, CSVUploadResponse
from orgmind.events.ingestion.normalizer import EventNormalizer
from orgmind.events.publisher import EventPublisher
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.models import ObjectModel

router = APIRouter()
normalizer = EventNormalizer()

@router.post("/webhook/{source}", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    source: str,
    payload: WebhookPayload,
    publisher: EventPublisher = Depends(get_event_publisher)
):
    """
    Receive and ingest a webhook event from an external source.
    """
    try:
        # Normalize event
        event = normalizer.normalize(source, payload.event_type, payload.payload)
        
        # Publish to event bus
        await publisher.publish(event)
        
        return IngestionResponse(
            status="accepted",
            event_id=str(event.event_id),
            message=f"Event from {source} queued for processing."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-csv", response_model=CSVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv( # type: ignore
    object_type_name: str,
    file: UploadFile = File(...),
    ontology_service: OntologyService = Depends(get_ontology_service),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file to bulk create objects.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV.")
    
    content = await file.read()
    text_content = content.decode("utf-8")
    
    objects_created = 0
    errors = []
    
    try:
        csv_reader = csv.DictReader(io.StringIO(text_content))
        
        # Look up object type by name
        all_types = ontology_service.list_object_types(db)
        target_type = next((t for t in all_types if t.name == object_type_name), None)
        
        if not target_type:
            raise HTTPException(status_code=404, detail=f"Object type '{object_type_name}' not found.")
            
        object_type_id = target_type.id
        
        # We need a tenant ID. For now using a hardcoded placeholder or generating one.
        # Ideally this comes from the authenticated user.
        # But CSV upload might be admin task.
        tenant_id = uuid4() 
        
        for row in csv_reader:
            try:
                # Filter empty keys
                clean_row = {k: v for k, v in row.items() if k and v}
                
                # Create ObjectModel
                obj_model = ObjectModel(
                    type_id=object_type_id,
                    data=clean_row
                    # ObjectModel doesn't have tenant_id column in current schema
                )

                await ontology_service.create_object(
                    session=db,
                    entity=obj_model,
                    tenant_id=tenant_id,
                    user_id=None
                )
                objects_created += 1
            except Exception as e:
                errors.append(f"Row error: {str(e)}")
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV processing error: {str(e)}")
        
    return CSVUploadResponse(
        status="completed" if not errors else "partial",
        objects_created=objects_created,
        errors=errors
    )
