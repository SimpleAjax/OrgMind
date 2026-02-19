import asyncio
import logging
import signal
import sys

from orgmind.platform.logging import configure_logging
from orgmind.platform.config import settings
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig
from orgmind.integrations.slack.service import SlackService
from orgmind.engine.nudge_engine import NudgeEngine

configure_logging()
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()

def handle_sigterm(*args):
    shutdown_event.set()

async def run_worker():
    postgres_config = PostgresConfig()
    postgres = PostgresAdapter(postgres_config)
    postgres.connect()
    
    slack = SlackService()
    engine = NudgeEngine(slack)
    
    logger.info("Nudge Worker started.")
    
    try:
        while not shutdown_event.is_set():
            try:
                await engine.check_and_dispatch_nudges(postgres)
            except Exception as e:
                logger.error(f"Error in nudge loop: {e}")
            
            # Wait 60s or until shutdown
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue
                
    finally:
        postgres.close()
        logger.info("Nudge Worker stopped.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    asyncio.run(run_worker())
