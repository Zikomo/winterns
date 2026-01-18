"""Database operations for execution - run lifecycle, deduplication, scheduling."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wintern.execution.models import RunStatus, SeenContent, WinternRun
from wintern.winterns.models import Wintern

# -----------------------------------------------------------------------------
# Run Lifecycle Operations
# -----------------------------------------------------------------------------


async def create_run(
    session: AsyncSession,
    wintern_id: uuid.UUID,
) -> WinternRun:
    """Create a new run record in PENDING status.

    Args:
        session: The database session.
        wintern_id: The ID of the wintern being executed.

    Returns:
        The newly created WinternRun.
    """
    run = WinternRun(
        wintern_id=wintern_id,
        status=RunStatus.PENDING,
    )
    session.add(run)
    await session.flush()
    return run


async def start_run(
    session: AsyncSession,
    run: WinternRun,
) -> WinternRun:
    """Mark a run as started (RUNNING status).

    Args:
        session: The database session.
        run: The run to start.

    Returns:
        The updated WinternRun.
    """
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.flush()
    return run


async def complete_run(
    session: AsyncSession,
    run: WinternRun,
    digest_content: str | None = None,
    metadata: dict | None = None,
) -> WinternRun:
    """Mark a run as completed successfully.

    Args:
        session: The database session.
        run: The run to complete.
        digest_content: The generated digest content.
        metadata: Additional metadata about the run.

    Returns:
        The updated WinternRun.
    """
    run.status = RunStatus.COMPLETED
    run.completed_at = datetime.now(UTC)
    run.digest_content = digest_content
    run.metadata_ = metadata
    await session.flush()
    return run


async def fail_run(
    session: AsyncSession,
    run: WinternRun,
    error_message: str,
    metadata: dict | None = None,
) -> WinternRun:
    """Mark a run as failed.

    Args:
        session: The database session.
        run: The run that failed.
        error_message: Description of the failure.
        metadata: Additional metadata about the run (partial results, etc.).

    Returns:
        The updated WinternRun.
    """
    run.status = RunStatus.FAILED
    run.completed_at = datetime.now(UTC)
    run.error_message = error_message
    run.metadata_ = metadata
    await session.flush()
    return run


# -----------------------------------------------------------------------------
# Run Query Operations
# -----------------------------------------------------------------------------


async def get_run_by_id(
    session: AsyncSession,
    run_id: uuid.UUID,
    wintern_id: uuid.UUID | None = None,
) -> WinternRun | None:
    """Get a run by its ID, optionally filtered by wintern.

    Args:
        session: The database session.
        run_id: The ID of the run.
        wintern_id: Optional wintern ID filter for ownership checks.

    Returns:
        The WinternRun if found, None otherwise.
    """
    stmt = select(WinternRun).where(WinternRun.id == run_id)
    if wintern_id is not None:
        stmt = stmt.where(WinternRun.wintern_id == wintern_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_runs_for_wintern(
    session: AsyncSession,
    wintern_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[WinternRun], int]:
    """List runs for a wintern with pagination.

    Args:
        session: The database session.
        wintern_id: The wintern to list runs for.
        skip: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        A tuple of (runs list, total count).
    """
    # Get total count
    count_stmt = (
        select(func.count()).select_from(WinternRun).where(WinternRun.wintern_id == wintern_id)
    )
    total = await session.scalar(count_stmt) or 0

    # Get paginated results, ordered by most recent first
    stmt = (
        select(WinternRun)
        .where(WinternRun.wintern_id == wintern_id)
        .order_by(WinternRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    return runs, total


# -----------------------------------------------------------------------------
# Content Deduplication Operations
# -----------------------------------------------------------------------------


def compute_content_hash(url: str) -> str:
    """Compute a SHA-256 hash of a URL for deduplication.

    Args:
        url: The URL to hash.

    Returns:
        A 64-character hexadecimal hash string.
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


async def get_seen_hashes(
    session: AsyncSession,
    wintern_id: uuid.UUID,
) -> set[str]:
    """Get all content hashes that have been seen for a wintern.

    Args:
        session: The database session.
        wintern_id: The wintern to check.

    Returns:
        A set of content hashes that have already been processed.
    """
    stmt = select(SeenContent.content_hash).where(SeenContent.wintern_id == wintern_id)
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def record_seen_content(
    session: AsyncSession,
    wintern_id: uuid.UUID,
    run_id: uuid.UUID,
    url: str,
    source_type: str,
) -> SeenContent:
    """Record that a piece of content has been seen.

    Args:
        session: The database session.
        wintern_id: The wintern that processed this content.
        run_id: The run during which this content was seen.
        url: The URL of the content.
        source_type: The source type (e.g., 'brave_search', 'reddit').

    Returns:
        The created SeenContent record.
    """
    content_hash = compute_content_hash(url)
    seen = SeenContent(
        wintern_id=wintern_id,
        run_id=run_id,
        content_hash=content_hash,
        source_type=source_type,
        source_url=url,
        seen_at=datetime.now(UTC),
    )
    session.add(seen)
    await session.flush()
    return seen


async def record_seen_content_batch(
    session: AsyncSession,
    wintern_id: uuid.UUID,
    run_id: uuid.UUID,
    items: list[tuple[str, str]],
) -> int:
    """Record multiple pieces of content as seen in a batch.

    Uses ON CONFLICT DO NOTHING to handle duplicates gracefully,
    which can occur with concurrent or manual+scheduled runs.

    Args:
        session: The database session.
        wintern_id: The wintern that processed this content.
        run_id: The run during which this content was seen.
        items: List of (url, source_type) tuples.

    Returns:
        The number of records inserted (excluding duplicates).
    """
    if not items:
        return 0

    now = datetime.now(UTC)
    values = [
        {
            "wintern_id": wintern_id,
            "run_id": run_id,
            "content_hash": compute_content_hash(url),
            "source_type": source_type,
            "source_url": url,
            "seen_at": now,
        }
        for url, source_type in items
    ]

    # Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING
    stmt = pg_insert(SeenContent).values(values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["wintern_id", "content_hash"])
    cursor_result = await session.execute(stmt)
    # rowcount returns the number of rows affected (inserted)
    # CursorResult has rowcount, but the async wrapper type doesn't expose it
    rowcount: int = getattr(cursor_result, "rowcount", 0) or 0
    return rowcount


# -----------------------------------------------------------------------------
# Scheduling Operations
# -----------------------------------------------------------------------------


async def get_due_winterns(
    session: AsyncSession,
    as_of: datetime | None = None,
) -> list[Wintern]:
    """Get all winterns that are due to run.

    A wintern is due if:
    - It is active (is_active=True)
    - It has a next_run_at time that is in the past

    Args:
        session: The database session.
        as_of: The time to check against. Defaults to now.

    Returns:
        List of Wintern models that are due to run.
    """
    if as_of is None:
        as_of = datetime.now(UTC)

    stmt = (
        select(Wintern)
        .where(
            Wintern.is_active == True,  # noqa: E712
            Wintern.next_run_at.isnot(None),
            Wintern.next_run_at <= as_of,
        )
        .options(
            selectinload(Wintern.source_configs),
            selectinload(Wintern.delivery_configs),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def calculate_next_run_at(
    cron_schedule: str,
    base_time: datetime | None = None,
) -> datetime:
    """Calculate the next run time based on a cron expression.

    Args:
        cron_schedule: A cron expression (e.g., "0 9 * * *" for 9am daily).
        base_time: The time to calculate from. Defaults to now.

    Returns:
        The next datetime when the wintern should run.
    """
    if base_time is None:
        base_time = datetime.now(UTC)

    cron = croniter(cron_schedule, base_time)
    next_time = cron.get_next(datetime)

    # Ensure timezone awareness
    if next_time.tzinfo is None:
        next_time = next_time.replace(tzinfo=UTC)

    return next_time


async def update_next_run_at(
    session: AsyncSession,
    wintern: Wintern,
) -> Wintern:
    """Update a wintern's next_run_at based on its cron schedule.

    Args:
        session: The database session.
        wintern: The wintern to update.

    Returns:
        The updated Wintern.
    """
    if wintern.cron_schedule:
        wintern.next_run_at = calculate_next_run_at(wintern.cron_schedule)
    else:
        wintern.next_run_at = None
    await session.flush()
    return wintern


# -----------------------------------------------------------------------------
# Wintern Loading Operations
# -----------------------------------------------------------------------------


async def get_wintern_for_execution(
    session: AsyncSession,
    wintern_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> Wintern | None:
    """Load a wintern with all relationships needed for execution.

    Args:
        session: The database session.
        wintern_id: The ID of the wintern.
        user_id: Optional user ID for ownership verification.

    Returns:
        The Wintern with source_configs and delivery_configs loaded,
        or None if not found.
    """
    stmt = (
        select(Wintern)
        .where(Wintern.id == wintern_id)
        .options(
            selectinload(Wintern.source_configs),
            selectinload(Wintern.delivery_configs),
        )
    )
    if user_id is not None:
        stmt = stmt.where(Wintern.user_id == user_id)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()
