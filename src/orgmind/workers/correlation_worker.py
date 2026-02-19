import asyncio
import logging
import signal
import sys

from orgmind.platform.logging import configure_logging
from orgmind.platform.config import settings
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig
from orgmind.engine.correlation_engine import CorrelationEngine

configure_logging()
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()

def handle_sigterm(*args):
    shutdown_event.set()

async def run_worker():
    postgres_config = PostgresConfig()
    postgres = PostgresAdapter(postgres_config)
    postgres.connect()
    
    engine = CorrelationEngine()
    
    logger.info("Correlation Worker started.")
    
    try:
        while not shutdown_event.is_set():
            try:
                # Engine is sync for now (process_correlations) because no async I/O except DB which is sync via adapter
                # But we should probably wrap it in run_in_executor if it's blocking
                # Or make engine async. 
                # PostgresAdapter is sync (SQLAlchemy sync).
                # So we run it directly, blocking loop for a bit. OK for worker.
                engine.process_correlations(postgres)
            except Exception as e:
                logger.error(f"Error in correlation loop: {e}")
            
            # Wait 60s
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue
                
    finally:
        postgres.close()
        logger.info("Correlation Worker stopped.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    asyncio.run(run_worker())
