import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session
from orgmind.storage.models_traces import DecisionTraceModel, ContextSuggestionModel
from orgmind.storage.models_context import NudgeLogModel
from orgmind.integrations.email.service import EmailService

logger = logging.getLogger(__name__)

class DigestEngine:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service

    def generate_and_send_digest(self, session: Session, user_email: str):
        """
        Generates stats and sends weekly digest to a specific user.
        """
        logger.info(f"Generating digest for {user_email}")
        
        # 1. Weekly Stats
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)
        
        # Total Traces
        total_traces = self._get_total_traces_count(session, user_email, week_start)
        
        if not total_traces:
            logger.info(f"No traces found for {user_email}, skipping digest.")
            return

        # Missing Context
        missing_context_traces = self._get_missing_context_traces(session, user_email, week_start)
        missing_count = len(missing_context_traces)
        
        # 2. Generate Content
        subject = f"Your Weekly OrgMind Decision Digest - {now.strftime('%Y-%m-%d')}"
        html_content = self._format_email(total_traces, missing_count, missing_context_traces[:5])
        
        # 3. Send
        self.email_service.send_html_email([user_email], subject, html_content)

    def _get_total_traces_count(self, session: Session, user_email: str, start_time: datetime) -> int:
        count = session.query(func.count(DecisionTraceModel.id)).filter(
            DecisionTraceModel.timestamp >= start_time,
            DecisionTraceModel.user_id == user_email
        ).scalar()
        return count or 0

    def _get_missing_context_traces(self, session: Session, user_email: str, start_time: datetime) -> List[DecisionTraceModel]:
        # Find IDs of traces with accepted suggestions
        accepted_traces_sq = session.query(ContextSuggestionModel.trace_id).filter(
            ContextSuggestionModel.status == 'accepted'
        ).subquery()
        
        return session.query(DecisionTraceModel).filter(
            DecisionTraceModel.timestamp >= start_time,
            DecisionTraceModel.user_id == user_email,
            DecisionTraceModel.status == 'success',
            ~DecisionTraceModel.id.in_(accepted_traces_sq)
        ).all()

    def _format_email(self, total: int, missing: int, sample_missing: List[DecisionTraceModel]) -> str:
        """
        Simple HTML template.
        """
        items_html = ""
        for trace in sample_missing:
            items_html += f"<li><b>{trace.action_type}</b> ({trace.timestamp.strftime('%a %H:%M')}) - <i>Missing Context</i></li>"
            
        return f"""
        <html>
        <body style="font-family: sans-serif;">
            <h2>Weekly Decision Summary</h2>
            <p>Here's what happened this week:</p>
            <ul>
                <li>Total Decisions Tracked: <b>{total}</b></li>
                <li>Decisions Missing Context: <b style="color: red;">{missing}</b></li>
            </ul>
            
            <h3>Action Required</h3>
            <p>The following recent actions are missing context. Please explain why they were taken:</p>
            <ul>
                {items_html}
            </ul>
            <p><a href="http://localhost:3000/decisions">View All Decisions</a></p>
        </body>
        </html>
        """
