"""Tests for the execution scheduler - APScheduler integration."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.execution.scheduler import (
    CHECK_INTERVAL_SECONDS,
    check_and_run_due_winterns,
    get_scheduler,
    setup_scheduler,
    shutdown_scheduler,
    start_scheduler,
)
from wintern.winterns.models import DeliveryConfig, DeliveryType, SourceConfig, SourceType, Wintern


class TestSetupScheduler:
    """Tests for scheduler setup."""

    def test_creates_asyncio_scheduler(self):
        """Should create an AsyncIOScheduler instance."""
        scheduler = setup_scheduler()

        assert scheduler is not None
        # Check it's configured
        assert scheduler.timezone is not None

    def test_scheduler_not_started(self):
        """Scheduler should not be running after setup."""
        scheduler = setup_scheduler()

        assert not scheduler.running


class TestStartScheduler:
    """Tests for starting the scheduler."""

    @pytest.mark.asyncio
    async def test_starts_scheduler(self):
        """Should start the scheduler and add check job."""
        scheduler = None
        try:
            scheduler = start_scheduler()

            assert scheduler.running
            # Check job was added
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == "check_due_winterns"

        finally:
            if scheduler:
                scheduler.shutdown(wait=False)
            # Reset global state
            from wintern.execution import scheduler as sched_module

            sched_module._scheduler = None

    @pytest.mark.asyncio
    async def test_returns_existing_scheduler_if_running(self):
        """Should return existing scheduler if already running."""
        scheduler1 = None
        try:
            scheduler1 = start_scheduler()
            scheduler2 = start_scheduler()

            assert scheduler1 is scheduler2

        finally:
            if scheduler1:
                scheduler1.shutdown(wait=False)
            from wintern.execution import scheduler as sched_module

            sched_module._scheduler = None


class TestShutdownScheduler:
    """Tests for shutting down the scheduler."""

    @pytest.mark.asyncio
    async def test_shuts_down_running_scheduler(self):
        """Should gracefully shutdown a running scheduler."""
        scheduler = start_scheduler()
        assert scheduler.running

        await shutdown_scheduler()

        # Verify global scheduler is cleared
        assert get_scheduler() is None

    @pytest.mark.asyncio
    async def test_handles_no_scheduler(self):
        """Should handle case where scheduler was never initialized."""
        # Reset global state first
        from wintern.execution import scheduler as sched_module

        sched_module._scheduler = None

        # Should not raise
        await shutdown_scheduler()


class TestGetScheduler:
    """Tests for getting the scheduler instance."""

    def test_returns_none_when_not_started(self):
        """Should return None when scheduler not initialized."""
        from wintern.execution import scheduler as sched_module

        sched_module._scheduler = None

        result = get_scheduler()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_scheduler_when_started(self):
        """Should return scheduler instance when started."""
        scheduler = None
        try:
            scheduler = start_scheduler()
            result = get_scheduler()

            assert result is scheduler

        finally:
            if scheduler:
                scheduler.shutdown(wait=False)
            from wintern.execution import scheduler as sched_module

            sched_module._scheduler = None


@pytest.fixture
async def test_user(test_session: AsyncSession):
    """Create a test user."""
    from wintern.auth.models import User

    user = User(
        id=uuid.uuid4(),
        email="scheduler-test@example.com",
        hashed_password="hashedpassword",
    )
    test_session.add(user)
    await test_session.flush()
    return user


@pytest.fixture
async def due_wintern(test_session: AsyncSession, test_user):
    """Create a wintern that is due to run."""
    wintern = Wintern(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Due Wintern",
        context="Test context",
        cron_schedule="* * * * *",
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        is_active=True,
    )
    test_session.add(wintern)
    await test_session.flush()

    # Add required configs
    source = SourceConfig(
        wintern_id=wintern.id,
        source_type=SourceType.BRAVE_SEARCH,
        config={},
        is_active=True,
    )
    test_session.add(source)

    delivery = DeliveryConfig(
        wintern_id=wintern.id,
        delivery_type=DeliveryType.SLACK,
        config={"webhook_url": "https://hooks.slack.com/test"},
        is_active=True,
    )
    test_session.add(delivery)
    await test_session.flush()

    return wintern


class TestCheckAndRunDueWinterns:
    """Tests for the scheduled job that checks for due winterns."""

    @pytest.mark.asyncio
    async def test_no_due_winterns(self):
        """Should handle case where no winterns are due."""
        with patch(
            "wintern.execution.scheduler.execution_service.get_due_winterns",
            return_value=[],
        ):
            # Should not raise
            await check_and_run_due_winterns()

    @pytest.mark.asyncio
    async def test_executes_due_winterns(self):
        """Should execute winterns that are due."""
        mock_wintern = MagicMock()
        mock_wintern.id = uuid.uuid4()
        mock_wintern.name = "Test Wintern"

        with (
            patch(
                "wintern.execution.scheduler.execution_service.get_due_winterns",
                return_value=[mock_wintern],
            ),
            patch(
                "wintern.execution.scheduler.execute_wintern",
                new_callable=AsyncMock,
                return_value=uuid.uuid4(),
            ) as mock_execute,
        ):
            await check_and_run_due_winterns()

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_on_execution_error(self):
        """Should continue executing other winterns if one fails."""
        mock_wintern1 = MagicMock()
        mock_wintern1.id = uuid.uuid4()
        mock_wintern1.name = "Wintern 1"

        mock_wintern2 = MagicMock()
        mock_wintern2.id = uuid.uuid4()
        mock_wintern2.name = "Wintern 2"

        from wintern.execution.executor import ExecutionError

        with (
            patch(
                "wintern.execution.scheduler.execution_service.get_due_winterns",
                return_value=[mock_wintern1, mock_wintern2],
            ),
            patch(
                "wintern.execution.scheduler.execute_wintern",
                new_callable=AsyncMock,
                side_effect=[ExecutionError("First failed"), uuid.uuid4()],
            ) as mock_execute,
        ):
            # Should not raise
            await check_and_run_due_winterns()

            # Both should have been attempted
            assert mock_execute.call_count == 2


class TestSchedulerConstants:
    """Tests for scheduler configuration constants."""

    def test_check_interval_is_reasonable(self):
        """Check interval should be reasonable (1-10 minutes)."""
        assert 60 <= CHECK_INTERVAL_SECONDS <= 600
        assert CHECK_INTERVAL_SECONDS == 300  # 5 minutes as specified
