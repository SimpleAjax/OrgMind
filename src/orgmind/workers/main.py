"""
OrgMind Worker Entry Point

This script launches background workers for the OrgMind platform.
Usage:
    python -m orgmind.workers.main [worker_name]

Available workers:
    - neo4j: Neo4j Index Worker
    - qdrant: Qdrant Index Worker
    - meili: Meilisearch Index Worker
    - all: Start all workers (default)
"""

import asyncio
import sys
from typing import List

from orgmind.platform.logging import configure_logging, get_logger
from orgmind.platform.config import settings
from orgmind.events import NatsEventBus
from orgmind.graph import Neo4jAdapter, Neo4jIndexWorker
from orgmind.storage.vector.qdrant import QdrantVectorStore
from orgmind.workers.qdrant_worker import QdrantIndexWorker
from orgmind.storage.search.meilisearch import MeiliSearchStore
from orgmind.workers.meili_worker import MeilisearchIndexWorker
from orgmind.workers.health import start_health_server

# Configure logging
configure_logging()
logger = get_logger(__name__)


class WorkerManager:
    """Manages the lifecycle of background workers."""
    
    def __init__(self):
        self.workers = []
        self.event_bus = None
        self.neo4j_adapter = None
        self.qdrant_store = None
        self.meili_store = None
        self._shutdown_event = asyncio.Event()
        
    async def start(self, worker_names: List[str]):
        """Start specified workers."""
        logger.info(f"Starting workers: {worker_names}")
        
        # Initialize shared resources
        self.event_bus = NatsEventBus(
            nats_url=settings.NATS_URL,
        )
        
        # Start health check server
        asyncio.create_task(start_health_server(self), name="health-check-server")
        
        # Connect to event bus
        await self.event_bus.connect()
        logger.info("Connected to Event Bus")
        
        should_start_all = "all" in worker_names
        
        # Initialize Neo4j Worker
        if should_start_all or "neo4j" in worker_names:
            await self._start_neo4j_worker()

        # Initialize Qdrant Worker
        if should_start_all or "qdrant" in worker_names:
            await self._start_qdrant_worker()

        # Initialize Meilisearch Worker
        if should_start_all or "meili" in worker_names:
            await self._start_meili_worker()
            
        # Keep running until shutdown
        await self._shutdown_event.wait()
        
    async def _start_neo4j_worker(self):
        """Initialize and start Neo4j Index Worker."""
        logger.info("Initializing Neo4j Index Worker...")
        
        self.neo4j_adapter = Neo4jAdapter(
            uri=settings.NEO4J_URI,
            username=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
        
        worker = Neo4jIndexWorker(
            event_bus=self.event_bus,
            neo4j_adapter=self.neo4j_adapter,
        )
        
        await worker.start()
        self.workers.append(worker)
        logger.info("Neo4j Index Worker started")

    async def _start_qdrant_worker(self):
        """Initialize and start Qdrant Index Worker."""
        logger.info("Initializing Qdrant Index Worker...")
        
        self.qdrant_store = QdrantVectorStore()
        # Note: connect() is called inside worker.start()
        
        worker = QdrantIndexWorker(
            event_bus=self.event_bus,
            vector_store=self.qdrant_store,
        )
        
        await worker.start()
        self.workers.append(worker)
        logger.info("Qdrant Index Worker started")

    async def _start_meili_worker(self):
        """Initialize and start Meilisearch Index Worker."""
        logger.info("Initializing Meilisearch Index Worker...")
        
        self.meili_store = MeiliSearchStore()
        
        worker = MeilisearchIndexWorker(
            event_bus=self.event_bus,
            search_store=self.meili_store,
        )
        
        await worker.start()
        self.workers.append(worker)
        logger.info("Meilisearch Index Worker started")

    async def shutdown(self):
        """Gracefully shutdown all workers."""
        logger.info("Shutting down workers...")
        
        # Stop all workers
        for worker in self.workers:
            try:
                await worker.stop()
            except Exception as e:
                logger.error(f"Error stopping worker: {e}")
                
        # Close shared resources
        if self.event_bus:
            await self.event_bus.disconnect()
            
        self._shutdown_event.set()
        logger.info("Workers shutdown complete")


async def main():
    """Main entry point."""
    # Parse arguments
    args = sys.argv[1:]
    worker_names = args if args else ["all"]
    
    manager = WorkerManager()
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(manager.shutdown()))
        
    try:
        await manager.start(worker_names)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        await manager.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            # Windows specific event loop policy/signal handling
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            # Windows does not support add_signal_handler in the same way for SelectorEventLoop
            asyncio.run(main()) 
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        pass
