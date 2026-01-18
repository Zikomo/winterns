"""APScheduler integration for scheduled wintern runs.

This module provides scheduler setup and management for automatically
running winterns based on their cron schedules.
"""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from wintern.core.database import async_session
from wintern.execution import service as execution_service
from wintern.execution.executor import ExecutionError, execute_wintern

log = structlog.get_logger()

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None

# Interval between checks for due winterns (in seconds)
CHECK_INTERVAL_SECONDS = 300  # 5 minutes


def setup_scheduler() -> AsyncIOScheduler:
    """Configure and create the AsyncIOScheduler.

    Returns:
        A configured AsyncIOScheduler (not yet started).
    """
    scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,  # Combine multiple pending runs into one
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 60,  # Allow 60 seconds grace time for misfires
        },
    )
    return scheduler


async def check_and_run_due_winterns() -> None:
    """Job that checks for and executes due winterns.

    This is the main scheduled job that runs every CHECK_INTERVAL_SECONDS.
    It queries for all winterns that are due to run and executes them.
    """
    log.debug("Checking for due winterns")

    async with async_session() as session:
        try:
            due_winterns = await execution_service.get_due_winterns(session)

            if not due_winterns:
                log.debug("No winterns due for execution")
                return

            log.info("Found due winterns", count=len(due_winterns))

            for wintern in due_winterns:
                try:
                    log.info(
                        "Executing scheduled wintern",
                        wintern_id=str(wintern.id),
                        wintern_name=wintern.name,
                    )
                    # Execute in the same session to maintain transaction
                    await execute_wintern(session, wintern.id)
                    await session.commit()
                    log.info(
                        "Scheduled wintern completed",
                        wintern_id=str(wintern.id),
                        wintern_name=wintern.name,
                    )
                except ExecutionError as e:
                    log.error(
                        "Scheduled wintern execution failed",
                        wintern_id=str(wintern.id),
                        wintern_name=wintern.name,
                        error=str(e),
                    )
                    await session.commit()  # Commit the failure record
                except Exception as e:
                    log.error(
                        "Unexpected error during scheduled execution",
                        wintern_id=str(wintern.id),
                        wintern_name=wintern.name,
                        error=str(e),
                    )
                    await session.rollback()

        except Exception as e:
            log.error("Error checking for due winterns", error=str(e))
            await session.rollback()


def start_scheduler() -> AsyncIOScheduler:
    """Start the scheduler and add the check job.

    Returns:
        The started scheduler instance.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        log.warning("Scheduler already running")
        return _scheduler

    _scheduler = setup_scheduler()

    # Add the check job
    _scheduler.add_job(
        check_and_run_due_winterns,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="check_due_winterns",
        name="Check and run due winterns",
        replace_existing=True,
    )

    _scheduler.start()
    log.info(
        "Scheduler started",
        check_interval_seconds=CHECK_INTERVAL_SECONDS,
    )

    return _scheduler


async def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully.

    Waits for any running jobs to complete before shutting down.
    """
    global _scheduler

    if _scheduler is None:
        log.debug("Scheduler not initialized, nothing to shutdown")
        return

    if not _scheduler.running:
        log.debug("Scheduler not running, nothing to shutdown")
        return

    log.info("Shutting down scheduler")
    _scheduler.shutdown(wait=True)
    _scheduler = None
    log.info("Scheduler shutdown complete")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the current scheduler instance.

    Returns:
        The scheduler if initialized, None otherwise.
    """
    return _scheduler
