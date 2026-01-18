"""Wintern API - Main application entry point."""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all models to register them with SQLAlchemy
from wintern.auth import models as auth_models  # noqa: F401
from wintern.auth.router import router as auth_router
from wintern.core.config import settings
from wintern.execution import models as execution_models  # noqa: F401
from wintern.execution.router import router as execution_router
from wintern.execution.scheduler import shutdown_scheduler, start_scheduler
from wintern.winterns import models as winterns_models  # noqa: F401
from wintern.winterns.router import router as winterns_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    log.info("Starting Wintern API", version=settings.version, environment=settings.environment)

    # Start the scheduler for background wintern execution
    start_scheduler()

    yield

    # Shutdown the scheduler gracefully
    await shutdown_scheduler()
    log.info("Shutting down Wintern API")


app = FastAPI(
    title="Wintern API",
    description="AI-powered web research agents that deliver personalized digests",
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(winterns_router)
app.include_router(execution_router)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.version,
        "environment": settings.environment,
    }
