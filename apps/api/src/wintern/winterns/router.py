"""API routes for Wintern CRUD operations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.auth.dependencies import current_user
from wintern.auth.models import User
from wintern.auth.service import get_async_session
from wintern.winterns import service as wintern_service
from wintern.winterns.schemas import (
    WinternCreate,
    WinternListResponse,
    WinternResponse,
    WinternUpdate,
)

router = APIRouter(prefix="/api/v1/winterns", tags=["winterns"])

AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
CurrentUserDep = Annotated[User, Depends(current_user)]


@router.get("", response_model=WinternListResponse)
async def list_winterns(
    session: AsyncSessionDep,
    user: CurrentUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WinternListResponse:
    """List all Winterns for the current user."""
    items, total = await wintern_service.list_winterns_for_user(
        session, user.id, skip=skip, limit=limit
    )
    return WinternListResponse(
        items=[WinternResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=WinternResponse, status_code=status.HTTP_201_CREATED)
async def create_wintern(
    data: WinternCreate,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> WinternResponse:
    """Create a new Wintern."""
    wintern = await wintern_service.create_wintern(session, user.id, data)
    return WinternResponse.model_validate(wintern)


@router.get("/{wintern_id}", response_model=WinternResponse)
async def get_wintern(
    wintern_id: uuid.UUID,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> WinternResponse:
    """Get a single Wintern by ID."""
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )
    return WinternResponse.model_validate(wintern)


@router.put("/{wintern_id}", response_model=WinternResponse)
async def update_wintern(
    wintern_id: uuid.UUID,
    data: WinternUpdate,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> WinternResponse:
    """Update a Wintern."""
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )
    updated = await wintern_service.update_wintern(session, wintern, data)
    return WinternResponse.model_validate(updated)


@router.delete("/{wintern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wintern(
    wintern_id: uuid.UUID,
    session: AsyncSessionDep,
    user: CurrentUserDep,
) -> None:
    """Soft delete a Wintern."""
    wintern = await wintern_service.get_wintern_by_id(session, wintern_id, user.id)
    if not wintern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wintern not found",
        )
    await wintern_service.delete_wintern(session, wintern)
