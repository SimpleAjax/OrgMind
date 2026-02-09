"""
OrgMind API Main Application

Entry point for the FastAPI application.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orgmind.platform.config import settings
from orgmind.platform.logging import configure_logging

# Configure logging on import
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    # TODO: Initialize database connections
    # TODO: Start event bus consumers
    # TODO: Initialize Temporal client
    yield
    # Shutdown
    # TODO: Close database connections
    # TODO: Stop event bus consumers


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
    
    TODO: Check all dependent services (DuckDB, Redis, Neo4j, etc.)
    """
    return {
        "status": "ready",
        "version": settings.VERSION,
        "checks": {
            "duckdb": "healthy",  # TODO: Actual check
            "redis": "healthy",  # TODO: Actual check
            "neo4j": "healthy",  # TODO: Actual check
        },
    }


# =============================================================================
# API ROUTERS (TODO: Add as components are implemented)
# =============================================================================

# from orgmind.api.routers import objects, types, links, rules, agents, workflows
# app.include_router(objects.router, prefix="/api/v1/objects", tags=["Objects"])
# app.include_router(types.router, prefix="/api/v1/types", tags=["Types"])
# app.include_router(links.router, prefix="/api/v1/links", tags=["Links"])
# app.include_router(rules.router, prefix="/api/v1/rules", tags=["Rules"])
# app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
# app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "orgmind.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
