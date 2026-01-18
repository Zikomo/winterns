"""API routes for wintern execution - manual triggers and run history."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.auth.dependencies import current_user
from wintern.auth.models import User
from wintern.auth.service import get_async_session
from wintern.core.database import async_session
from wintern.execution import service as execution_service
from wintern.execution.executor import ExecutionError, execute_wintern
from wintern.execution.schemas import (
    TriggerRunResponse,
    WinternRunListResponse,
    WinternRunResponse,
)
from wintern.winterns import service as wintern_service

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/winterns", tags=["execution"])

AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
CurrentUserDep = Annotated[User, Depends(current_user)]


async def run_wintern_background(wintern_id: uuid.UUID) -> None:
    """Background task to execute a wintern.

    This creates its own database session since it runs outside the
    request context.

    Args:
        wintern_id: The ID of the wintern to execute.
    """
    log.info("Starting background wintern execution", wintern_id=str(wintern_id))

    async with async_session() as session:
        try:
            run_id = await execute_wintern(session, wintern_id)
            await session.commit()
            log.info(
                "Background wintern execution completed",
                wintern_id=str(wintern_id),
                run_id=str(run_id),
            )
        except ExecutionError as e:
            log.error(
                "Background wintern execution failed",
                wintern_id=str(wintern_id),
                error=str(e),
            )
            await session.commit()  # Commit the failure record
        except Exception as e:
            log.error(
                "Unexpected error in background execution",
                wintern_id=str(wintern_id),
                error=str(e),
            )
            await session.rollback()


@router.post(
    "/{wintern_id}/run",
    response_model=TriggerRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_run(
    wintern_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> TriggerRunResponse:
    """Trigger a manual run of a wintern.

    This endpoint immediately creates a run record and schedules the
    actual execution in the background, returning 202 Accepted.

    The run can be monitored using GET /api/v1/winterns/{id}/runs/{run_id}.
    """
    # Verify wintern exists and belongs to user
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )

    # Check for active sources and delivery channels upfront
    active_sources = [s for s in wintern.source_configs if s.is_active]
    active_deliveries = [d for d in wintern.delivery_configs if d.is_active]

    if not active_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active sources configured for this wintern",
        )

    if not active_deliveries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active delivery channels configured for this wintern",
        )

    # Schedule background execution - run record will be created by execute_wintern
    background_tasks.add_task(run_wintern_background, wintern_id)

    log.info(
        "Manual run triggered",
        wintern_id=str(wintern_id),
        user_id=str(user.id),
    )

    return TriggerRunResponse(
        wintern_id=wintern_id,
        message="Execution has been queued. Check the runs list for status.",
    )


@router.get(
    "/{wintern_id}/runs",
    response_model=WinternRunListResponse,
)
async def list_runs(
    wintern_id: uuid.UUID,
    session: AsyncSessionDep,
    user: CurrentUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WinternRunListResponse:
    """List runs for a wintern with pagination.

    Results are ordered by most recent first.
    """
    # Verify wintern exists and belongs to user
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )

    runs, total = await execution_service.list_runs_for_wintern(
        session, wintern_id, skip=skip, limit=limit
    )

    return WinternRunListResponse(
        items=[WinternRunResponse.model_validate(run) for run in runs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{wintern_id}/runs/{run_id}",
    response_model=WinternRunResponse,
)
async def get_run(
    wintern_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> WinternRunResponse:
    """Get details of a specific run."""
    # Verify wintern exists and belongs to user
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )

    # Get the run, ensuring it belongs to this wintern
    run = await execution_service.get_run_by_id(session, run_id, wintern_id=wintern_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    return WinternRunResponse.model_validate(run)
