"""
Health check server for OrgMind workers.
"""

import asyncio
from typing import Dict, Any

from fastapi import FastAPI
from uvicorn import Config, Server

from orgmind.platform.config import settings
from orgmind.platform.logging import get_logger

logger = get_logger(__name__)



def create_health_app(manager: Any) -> FastAPI:
    """Create FastAPI application for health checks."""
    app = FastAPI(title="OrgMind Worker Health", version=settings.VERSION)
    
    @app.get("/health")
    async def health() -> Dict[str, Any]:
        """Health check endpoint."""
        checks = {}
        is_healthy = True
        
        # Check Event Bus
        if manager.event_bus:
            try:
                bus_healthy = await manager.event_bus.health_check()
                checks["nats"] = "healthy" if bus_healthy else "unhealthy"
                if not bus_healthy:
                    is_healthy = False
            except Exception as e:
                checks["nats"] = f"error: {str(e)}"
                is_healthy = False
        else:
            checks["nats"] = "unknown"

        # Check Neo4j
        if manager.neo4j_adapter:
            try:
                neo4j_healthy = manager.neo4j_adapter.health_check()
                checks["neo4j"] = "healthy" if neo4j_healthy else "unhealthy"
                if not neo4j_healthy:
                    is_healthy = False
            except Exception as e:
                checks["neo4j"] = f"error: {str(e)}"
                is_healthy = False
        
        # Check Qdrant
        if manager.qdrant_store:
            try:
                qdrant_healthy = await manager.qdrant_store.health_check()
                checks["qdrant"] = "healthy" if qdrant_healthy else "unhealthy"
                if not qdrant_healthy:
                    is_healthy = False
            except Exception as e:
                checks["qdrant"] = f"error: {str(e)}"
                is_healthy = False
                
        # Check Meilisearch
        if manager.meili_store:
            try:
                meili_healthy = await manager.meili_store.health_check()
                checks["meilisearch"] = "healthy" if meili_healthy else "unhealthy"
                if not meili_healthy:
                    is_healthy = False
            except Exception as e:
                checks["meilisearch"] = f"error: {str(e)}"
                is_healthy = False

        return {
            "status": "alive" if is_healthy else "degraded",
            "version": settings.VERSION,
            "checks": checks
        }
    
    return app


async def start_health_server(manager: Any, port: int | None = None) -> None:
    """
    Start a lightweight HTTP server for health checks.
    
    Args:
        manager: The WorkerManager instance containing adapters and event bus.
        port: Port to listen on (defauts to settings.WORKER_HEALTH_PORT).
    """
    app = create_health_app(manager)

    # Configure Uvicorn
    listen_port = port or settings.WORKER_HEALTH_PORT
    logger.info(f"Starting health check server on port {listen_port}")
    
    config = Config(
        app=app, 
        host="0.0.0.0", 
        port=listen_port,
        log_level="error", # Keep logs quiet
        loop="asyncio"
    )
    server = Server(config)
    
    await server.serve()
