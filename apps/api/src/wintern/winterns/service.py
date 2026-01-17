"""Business logic for Wintern CRUD operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wintern.winterns.models import DeliveryConfig, SourceConfig, Wintern
from wintern.winterns.schemas import WinternCreate, WinternUpdate


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


async def create_wintern(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: WinternCreate,
) -> Wintern:
    """Create a new Wintern with its source and delivery configs."""
    wintern = Wintern(
        user_id=user_id,
        name=data.name,
        description=data.description,
        context=data.context,
        cron_schedule=data.cron_schedule,
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

    for field, value in update_data.items():
        setattr(wintern, field, value)

    await session.commit()
    await session.refresh(wintern)
    return wintern


async def delete_wintern(
    session: AsyncSession,
    wintern: Wintern,
) -> None:
    """Soft delete a Wintern by setting is_active to False."""
    wintern.is_active = False
    await session.commit()
