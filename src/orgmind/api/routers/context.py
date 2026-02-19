from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from orgmind.api.dependencies import get_postgres_adapter
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.storage.models_context import ContextEventModel, ContextSourceType

router = APIRouter()

class ContextCaptureRequest(BaseModel):
    source: ContextSourceType
    source_id: str
    content: Dict[str, Any]
    timestamp: Optional[datetime] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ContextEventResponse(BaseModel):
    id: str
    source: str
    source_id: str
    created_at: datetime
    timestamp: datetime
    content: Dict[str, Any]
    
    class Config:
        from_attributes = True

@router.post("/capture", response_model=ContextEventResponse)
def capture_context(
    request: ContextCaptureRequest,
    background_tasks: BackgroundTasks,
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    """
    Capture a single context event from an external source.
    """
    event_id = str(uuid.uuid4())
    
    with postgres.get_session() as session:
        event = ContextEventModel(
            id=event_id,
            source=request.source.value,
            source_id=request.source_id,
            content=request.content,
            user_id=request.user_id,
            session_id=request.session_id,
            timestamp=request.timestamp or datetime.utcnow()
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        
        # TODO: Trigger correlation in background?
        # background_tasks.add_task(correlate_context, event_id)
        
        return ContextEventResponse.model_validate(event)

@router.post("/batch", response_model=List[ContextEventResponse])
def batch_capture_context(
    requests: List[ContextCaptureRequest],
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    """
    Bulk capture context events.
    """
    events = []
    with postgres.get_session() as session:
        for req in requests:
            event = ContextEventModel(
                id=str(uuid.uuid4()),
                source=req.source.value,
                source_id=req.source_id,
                content=req.content,
                user_id=req.user_id,
                session_id=req.session_id,
                timestamp=req.timestamp or datetime.utcnow()
            )
            session.add(event)
            events.append(event)
        session.commit()
        
        # Refresh all to get created_at etc
        for e in events:
            session.refresh(e)
            
        return [ContextEventResponse.model_validate(e) for e in events]

@router.get("/recent", response_model=List[ContextEventResponse])
def get_recent_context(
    limit: int = 50,
    source: Optional[ContextSourceType] = None,
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    """
    Get recent context events. Useful for debugging or manual correlation checks.
    """
    with postgres.get_session() as session:
        query = session.query(ContextEventModel).order_by(ContextEventModel.timestamp.desc())
        
        if source:
            query = query.filter(ContextEventModel.source == source.value)
            
        events = query.limit(limit).all()
        return [ContextEventResponse.model_validate(e) for e in events]
