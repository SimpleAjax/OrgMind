from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class WebhookPayload(BaseModel):
    """Generic payload for webhooks. Actual structure depends on source."""
    source: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None

class IngestionResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    message: Optional[str] = None

class CSVUploadResponse(BaseModel):
    status: str
    objects_created: int
    errors: List[str] = []
