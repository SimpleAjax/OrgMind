import asyncio
import logging
import signal
import sys
from sqlalchemy import distinct

from orgmind.platform.logging import configure_logging
from orgmind.platform.config import settings
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig
from orgmind.integrations.email.service import EmailService
from orgmind.engine.digest_engine import DigestEngine
from orgmind.storage.models_traces import DecisionTraceModel
from datetime import datetime, timedelta

configure_logging()
logger = logging.getLogger(__name__)

async def run_digest_job():
    postgres_config = PostgresConfig()
    postgres = PostgresAdapter(postgres_config)
    postgres.connect()
    
    email_service = EmailService()
    engine = DigestEngine(email_service)
    
    logger.info("Starting Digest Job...")
    
    try:
        with postgres.get_session() as session:
            # Find all users active in last week
            week_start = datetime.utcnow() - timedelta(days=7)
            users = session.query(distinct(DecisionTraceModel.user_id)).filter(
                DecisionTraceModel.timestamp >= week_start
            ).all()
            
            for user_row in users:
                user_email = user_row[0]
                if user_email and "@" in user_email: # Simple email check
                    try:
                        engine.generate_and_send_digest(session, user_email)
                    except Exception as e:
                        logger.error(f"Failed to generate digest for {user_email}: {e}")
                        
    finally:
        postgres.close()
        logger.info("Digest Job Completed.")

if __name__ == "__main__":
    # For MVP, this script runs once and exits.
    # Can be scheduled via cron or Temporal later.
    asyncio.run(run_digest_job())
