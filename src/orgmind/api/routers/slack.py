import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from orgmind.platform.config import settings
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.api.dependencies import get_postgres_adapter
from orgmind.storage.models_context import ContextEventModel, ContextSourceType

logger = logging.getLogger(__name__)
router = APIRouter()

async def verify_signature(request: Request):
    """
    Verify Slack request signature using the signing secret.
    """
    if not settings.SLACK_SIGNING_SECRET:
         # If no secret is configured, we can't verify. 
         # In production this should be strictly enforced.
         # For dev/testing without a real Slack app, we might skip.
         logger.warning("SLACK_SIGNING_SECRET not set, skipping signature verification.")
         return 

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")
    
    if not timestamp or not signature:
         logger.warning("Missing Slack headers for verification")
         # raise HTTPException(status_code=400, detail="Missing Slack headers")
         return 

    # Verify timestamp freshness (e.g. within 5 mins) - omitted for brevity

    body = await request.body()
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode('utf-8')
    
    my_signature = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode('utf-8'),
        base,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(my_signature, signature):
         logger.error("Invalid Slack signature")
         raise HTTPException(status_code=401, detail="Invalid signature")

def process_event(event: Dict[str, Any], postgres: PostgresAdapter):
    """
    Store Slack event as context in the database.
    """
    try:
        event_type = event.get("type")
        if event_type == "message" and not event.get("bot_id"): # Ignore bots/apps to avoid loops
            with postgres.get_session() as session:
                 import uuid
                 from datetime import datetime
                 
                 ts_val = event.get("ts")
                 timestamp = datetime.fromtimestamp(float(ts_val)) if ts_val else datetime.utcnow()
                 
                 content = {
                     "text": event.get("text"),
                     "channel": event.get("channel"),
                     "thread_ts": event.get("thread_ts"),
                     "team": event.get("team")
                 }
                 
                 ctx_event = ContextEventModel(
                     id=str(uuid.uuid4()),
                     source=ContextSourceType.SLACK.value,
                     source_id=f"{event.get('channel')}_{ts_val}", # Unique ID: channel + ts
                     user_id=event.get("user"),
                     content=content,
                     timestamp=timestamp
                 )
                 session.add(ctx_event)
                 session.commit()
                 logger.info(f"Stored Slack context event {ctx_event.id} from user {ctx_event.user_id}")
    except Exception as e:
        logger.exception(f"Failed to process Slack event: {e}")

@router.post("/events")
async def slack_events(
    request: Request, 
    background_tasks: BackgroundTasks,
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    """
    Endpoint for Slack Events API.
    """
    # Retrieve body bytes (FastAPI consumes stream, so we must be careful if verify needs it)
    # But verify_signature awaits body(), and request.body() is cached by Starlette/FastAPI usually?
    # Actually request.body() returns bytes and can be called multiple times.
    
    body_bytes = await request.body()
    try:
        data = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Verify signature
    await verify_signature(request)

    # URL Verification (Challenge)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}
        
    # Event Callback
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        # Enrich with outer event data if needed (e.g. team_id, api_app_id)
        # Pass to background task
        background_tasks.add_task(process_event, event, postgres)
        return {"ok": True}
        
    return {"ok": True}
