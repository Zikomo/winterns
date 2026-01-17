"""Wintern API - Main application entry point."""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wintern.core.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    log.info("Starting Wintern API", version=settings.version, environment=settings.environment)
    yield
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


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.version,
        "environment": settings.environment,
    }
