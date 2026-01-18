"""Pydantic schemas for execution API responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from wintern.execution.models import RunStatus


class WinternRunResponse(BaseModel):
    """API response schema for a single wintern run."""

    id: uuid.UUID = Field(..., description="Unique identifier for the run")
    wintern_id: uuid.UUID = Field(..., description="ID of the wintern that was executed")
    status: RunStatus = Field(..., description="Current status of the run")
    started_at: datetime | None = Field(default=None, description="When the run started")
    completed_at: datetime | None = Field(default=None, description="When the run completed")
    error_message: str | None = Field(default=None, description="Error message if the run failed")
    digest_content: str | None = Field(default=None, description="The generated digest content")
    metadata_: dict | None = Field(
        default=None,
        serialization_alias="metadata",
        description="Additional run metadata (source counts, delivery results, etc.)",
    )
    created_at: datetime = Field(..., description="When the run record was created")
    updated_at: datetime = Field(..., description="When the run record was last updated")

    model_config = {"from_attributes": True, "populate_by_name": True}


class WinternRunListResponse(BaseModel):
    """Paginated list of wintern runs."""

    items: list[WinternRunResponse] = Field(..., description="List of runs for this page")
    total: int = Field(..., ge=0, description="Total number of runs")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items per page")


class TriggerRunResponse(BaseModel):
    """Response when triggering a manual run.

    Note: The run record is created by the background task, not the API.
    Use the list runs endpoint to find runs for a wintern.
    """

    wintern_id: uuid.UUID = Field(..., description="ID of the wintern being executed")
    message: str = Field(..., description="Human-readable message about the trigger")
