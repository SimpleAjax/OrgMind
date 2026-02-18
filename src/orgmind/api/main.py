"""
OrgMind API Main Application

Entry point for the FastAPI application.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from orgmind.platform.config import settings
from orgmind.platform.logging import configure_logging, get_logger
from orgmind.api.routers import objects, types, rules, agents
from orgmind.api.dependencies import (
    init_resources,
    close_resources,
    get_postgres_adapter,
    get_event_bus,
)

# Configure logging on import
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting OrgMind API...")
    try:
        await init_resources()
        logger.info("Resources initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize resources: {e}")
        # We might want to let it fail or continue with degraded state?
        # Typically fail fast for critical deps.
        raise # Let it crash if DB/NATS are down at startup
    
    yield
    
    # Shutdown
    logger.info("Shutting down OrgMind API...")
    await close_resources()
    logger.info("Resources closed.")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Context Graph Platform for Organizational Intelligence",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# OBSERVABILITY
# =============================================================================

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# =============================================================================
# HEALTH ENDPOINTS
# =============================================================================


@app.get("/health/live", tags=["Health"])
async def liveness() -> dict:
    """Liveness probe - is the service running?"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness() -> dict:
    """
    Readiness probe - is the service ready to accept traffic?
    Checks database and event bus connections.
    """
    # Check Postgres
    postgres_healthy = False
    try:
        adapter = get_postgres_adapter()
        postgres_healthy = adapter.health_check()
    except Exception:
        pass
    
    # Check NATS
    nats_healthy = False
    try:
        bus = get_event_bus()
        nats_healthy = await bus.health_check()
    except Exception:
        pass
    
    status_code = "ready" if (postgres_healthy and nats_healthy) else "not_ready"
    
    return {
        "status": status_code,
        "version": settings.VERSION,
        "checks": {
            "postgres": "healthy" if postgres_healthy else "unhealthy",
            "nats": "healthy" if nats_healthy else "unhealthy",
        },
    }


# =============================================================================
# API ROUTERS
# =============================================================================

# from orgmind.api.routers import objects, types, links, rules, agents, workflows
# app.include_router(links.router, prefix="/api/v1/links", tags=["Links"])
# app.include_router(rules.router, prefix="/api/v1/rules", tags=["Rules"])
# app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
# app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
app.include_router(objects.router, prefix="/api/v1/objects", tags=["Objects"])
app.include_router(types.router, prefix="/api/v1/types", tags=["Types"])
app.include_router(rules.router, prefix="/api/v1/rules", tags=["Rules"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "orgmind.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
