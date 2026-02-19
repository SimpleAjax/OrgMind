import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from orgmind.storage.models_traces import DecisionTraceModel, ContextSuggestionModel
from orgmind.storage.models_context import NudgeLogModel
from orgmind.integrations.slack.service import SlackService
from orgmind.storage.postgres_adapter import PostgresAdapter
import uuid

logger = logging.getLogger(__name__)

class NudgeEngine:
    def __init__(self, slack_service: SlackService):
        self.slack_service = slack_service

    async def check_and_dispatch_nudges(self, postgres: PostgresAdapter):
        """
        Main loop: Find traces needing context and nudge users.
        """
        logger.info("Running Nudge Engine check...")
        
        with postgres.get_session() as session:
            # 1. Find candidates
            now = datetime.utcnow()
            window_start = now - timedelta(hours=1)
            window_end = now - timedelta(minutes=5)
            
            # Query for traces in window that are success and have user
            traces = session.query(DecisionTraceModel).filter(
                DecisionTraceModel.timestamp >= window_start,
                DecisionTraceModel.timestamp <= window_end,
                DecisionTraceModel.status == "success",
                DecisionTraceModel.user_id.isnot(None)
            ).all()
            
            logger.debug(f"Found {len(traces)} potential traces for nudging.")
            
            for trace in traces:
                if self._needs_nudge(session, trace):
                    await self._dispatch_nudge(session, trace)

    def _needs_nudge(self, session: Session, trace: DecisionTraceModel) -> bool:
        # Check if already nudged
        existing_nudge = session.query(NudgeLogModel).filter_by(trace_id=trace.id).first()
        if existing_nudge:
            return False
            
        # Check if context already exists (accepted suggestion)
        accepted = session.query(ContextSuggestionModel).filter_by(
            trace_id=trace.id, 
            status="accepted"
        ).first()
        
        if accepted:
            return False
            
        return True

    async def _dispatch_nudge(self, session: Session, trace: DecisionTraceModel):
        user_id = trace.user_id
        if not user_id: 
            return
            
        logger.info(f"Dispatching nudge for trace {trace.id} to user {user_id}")

        # Try to resolve Slack ID if user_id looks like email
        slack_user_id = user_id
        if "@" in user_id:
            # Assuming SlackService has lookup (placeholder or implemented)
            # user_info = await self.slack_service.lookup_user_by_email(user_id)
            # For now we use user_id directly if it looks like a slack ID (U...) 
            # or try to send to email if Slack supports it (it doesn't directly via chat.postMessage usually without ID).
            # If user_id is email, we skip for now unless lookup is implemented.
            # Let's assume user_id is Slack ID for MVP or we log warning.
            pass

        action = trace.action_type
        # TODO: Add link to verify/add context UI
        text = f"Hey! You recently performed *{action}*. Could you briefly explain why? Please reply to this thread."

        sent = await self.slack_service.send_dm(slack_user_id, text)
        
        # Log the nudge
        nudge_status = "sent" if sent else "failed"
        nudge = NudgeLogModel(
            id=str(uuid.uuid4()),
            trace_id=trace.id,
            user_id=user_id,
            channel="slack",
            status=nudge_status
        )
        session.add(nudge)
        session.commit()
        
        if sent:
            logger.info(f"Nudge sent to {user_id} for trace {trace.id}")
        else:
            logger.error(f"Failed to send nudge to {user_id}")
