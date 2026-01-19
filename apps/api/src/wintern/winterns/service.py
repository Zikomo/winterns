"""Business logic for Wintern CRUD operations."""

import uuid
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wintern.execution.service import calculate_next_run_at
from wintern.winterns.models import DeliveryConfig, SourceConfig, Wintern
from wintern.winterns.schemas import WinternCreate, WinternUpdate


@dataclass
class WinternCounts:
    """Aggregate counts for a user's winterns."""

    active_count: int
    paused_count: int
    scheduled_count: int


async def get_wintern_by_id(
    session: AsyncSession,
    wintern_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Wintern | None:
    """Get a single Wintern by ID, ensuring it belongs to the user."""
    result = await session.execute(
        select(Wintern)
        .options(selectinload(Wintern.source_configs), selectinload(Wintern.delivery_configs))
        .where(Wintern.id == wintern_id, Wintern.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_winterns_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Wintern], int]:
    """List Winterns for a user with pagination."""
    # Get total count
    count_result = await session.execute(
        select(func.count()).select_from(Wintern).where(Wintern.user_id == user_id)
    )
    total = count_result.scalar_one()

    # Get paginated items
    result = await session.execute(
        select(Wintern)
        .options(selectinload(Wintern.source_configs), selectinload(Wintern.delivery_configs))
        .where(Wintern.user_id == user_id)
        .order_by(Wintern.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return items, total


async def get_wintern_counts(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> WinternCounts:
    """Get aggregate counts for a user's winterns."""
    result = await session.execute(
        select(
            func.count(case((Wintern.is_active == True, 1))).label("active_count"),  # noqa: E712
            func.count(case((Wintern.is_active == False, 1))).label("paused_count"),  # noqa: E712
            func.count(case((Wintern.next_run_at != None, 1))).label("scheduled_count"),  # noqa: E711
        ).where(Wintern.user_id == user_id)
    )
    row = result.one()
    return WinternCounts(
        active_count=row.active_count,
        paused_count=row.paused_count,
        scheduled_count=row.scheduled_count,
    )


async def create_wintern(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: WinternCreate,
) -> Wintern:
    """Create a new Wintern with its source and delivery configs."""
    # Calculate next_run_at if cron_schedule is provided
    next_run_at = None
    if data.cron_schedule:
        next_run_at = calculate_next_run_at(data.cron_schedule)

    wintern = Wintern(
        user_id=user_id,
        name=data.name,
        description=data.description,
        context=data.context,
        cron_schedule=data.cron_schedule,
        next_run_at=next_run_at,
    )
    session.add(wintern)
    await session.flush()  # Get the wintern ID

    # Create source configs
    for source_config_data in data.source_configs:
        source_config = SourceConfig(
            wintern_id=wintern.id,
            source_type=source_config_data.source_type,
            config=source_config_data.config,
            is_active=source_config_data.is_active,
        )
        session.add(source_config)

    # Create delivery configs
    for delivery_config_data in data.delivery_configs:
        delivery_config = DeliveryConfig(
            wintern_id=wintern.id,
            delivery_type=delivery_config_data.delivery_type,
            config=delivery_config_data.config,
            is_active=delivery_config_data.is_active,
        )
        session.add(delivery_config)

    await session.commit()
    await session.refresh(wintern)

    # Reload with relationships
    return await get_wintern_by_id(session, wintern.id, user_id)  # type: ignore[return-value]


async def update_wintern(
    session: AsyncSession,
    wintern: Wintern,
    data: WinternUpdate,
) -> Wintern:
    """Update an existing Wintern."""
    update_data = data.model_dump(exclude_unset=True)

    # Apply the updates
    for field, value in update_data.items():
        setattr(wintern, field, value)

    # Only update next_run_at when is_active or cron_schedule changes
    if "is_active" in update_data or "cron_schedule" in update_data:
        if wintern.is_active and wintern.cron_schedule:
            wintern.next_run_at = calculate_next_run_at(wintern.cron_schedule)
        else:
            wintern.next_run_at = None

    await session.commit()
    await session.refresh(wintern)
    return wintern


async def delete_wintern(
    session: AsyncSession,
    wintern: Wintern,
) -> None:
    """Soft delete a Wintern by setting is_active to False."""
    wintern.is_active = False
    wintern.next_run_at = None
    await session.commit()
