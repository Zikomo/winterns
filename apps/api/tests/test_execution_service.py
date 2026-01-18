"""Tests for execution service - hash computation, run lifecycle, deduplication."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.execution import service as execution_service
from wintern.execution.models import RunStatus
from wintern.winterns.models import DeliveryConfig, DeliveryType, SourceConfig, SourceType, Wintern


@pytest.fixture
async def test_user(test_session: AsyncSession):
    """Create a test user."""
    from wintern.auth.models import User

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashedpassword",
    )
    test_session.add(user)
    await test_session.flush()
    return user


@pytest.fixture
async def test_wintern(test_session: AsyncSession, test_user):
    """Create a test wintern."""
    wintern = Wintern(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Wintern",
        context="Test research context",
        cron_schedule="0 9 * * *",
        is_active=True,
    )
    test_session.add(wintern)
    await test_session.flush()
    return wintern


@pytest.fixture
async def test_wintern_with_configs(test_session: AsyncSession, test_user):
    """Create a test wintern with source and delivery configs."""
    wintern = Wintern(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Wintern With Configs",
        context="Test research context",
        cron_schedule="0 9 * * *",
        is_active=True,
    )
    test_session.add(wintern)
    await test_session.flush()

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


class TestContentHashComputation:
    """Tests for compute_content_hash."""

    def test_compute_hash_returns_sha256(self):
        """Hash should be 64 character hex string (SHA-256)."""
        url = "https://example.com/article"
        hash_result = execution_service.compute_content_hash(url)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_hash_deterministic(self):
        """Same URL should produce same hash."""
        url = "https://example.com/article"
        hash1 = execution_service.compute_content_hash(url)
        hash2 = execution_service.compute_content_hash(url)

        assert hash1 == hash2

    def test_compute_hash_different_urls(self):
        """Different URLs should produce different hashes."""
        url1 = "https://example.com/article1"
        url2 = "https://example.com/article2"

        hash1 = execution_service.compute_content_hash(url1)
        hash2 = execution_service.compute_content_hash(url2)

        assert hash1 != hash2


class TestRunLifecycle:
    """Tests for run creation and status updates."""

    @pytest.mark.asyncio
    async def test_create_run(self, test_session: AsyncSession, test_wintern):
        """Should create a run in PENDING status."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        assert run.id is not None
        assert run.wintern_id == test_wintern.id
        assert run.status == RunStatus.PENDING
        assert run.started_at is None
        assert run.completed_at is None

    @pytest.mark.asyncio
    async def test_start_run(self, test_session: AsyncSession, test_wintern):
        """Should mark run as RUNNING with start time."""
        run = await execution_service.create_run(test_session, test_wintern.id)
        started_run = await execution_service.start_run(test_session, run)

        assert started_run.status == RunStatus.RUNNING
        assert started_run.started_at is not None
        assert started_run.completed_at is None

    @pytest.mark.asyncio
    async def test_complete_run(self, test_session: AsyncSession, test_wintern):
        """Should mark run as COMPLETED with digest and metadata."""
        run = await execution_service.create_run(test_session, test_wintern.id)
        await execution_service.start_run(test_session, run)

        digest = "Test digest content"
        metadata = {"total_searched": 10, "curated": 5}

        completed_run = await execution_service.complete_run(
            test_session, run, digest_content=digest, metadata=metadata
        )

        assert completed_run.status == RunStatus.COMPLETED
        assert completed_run.completed_at is not None
        assert completed_run.digest_content == digest
        assert completed_run.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_fail_run(self, test_session: AsyncSession, test_wintern):
        """Should mark run as FAILED with error message."""
        run = await execution_service.create_run(test_session, test_wintern.id)
        await execution_service.start_run(test_session, run)

        error_message = "Test error"
        failed_run = await execution_service.fail_run(
            test_session, run, error_message=error_message
        )

        assert failed_run.status == RunStatus.FAILED
        assert failed_run.completed_at is not None
        assert failed_run.error_message == error_message


class TestRunQueries:
    """Tests for run query operations."""

    @pytest.mark.asyncio
    async def test_get_run_by_id(self, test_session: AsyncSession, test_wintern):
        """Should retrieve run by ID."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        found_run = await execution_service.get_run_by_id(test_session, run.id)

        assert found_run is not None
        assert found_run.id == run.id

    @pytest.mark.asyncio
    async def test_get_run_by_id_not_found(self, test_session: AsyncSession):
        """Should return None for non-existent run."""
        fake_id = uuid.uuid4()

        found_run = await execution_service.get_run_by_id(test_session, fake_id)

        assert found_run is None

    @pytest.mark.asyncio
    async def test_get_run_by_id_with_wintern_filter(
        self, test_session: AsyncSession, test_wintern, test_user
    ):
        """Should filter by wintern_id when provided."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        # Should find with correct wintern_id
        found_run = await execution_service.get_run_by_id(
            test_session, run.id, wintern_id=test_wintern.id
        )
        assert found_run is not None

        # Should not find with wrong wintern_id
        found_run = await execution_service.get_run_by_id(
            test_session, run.id, wintern_id=uuid.uuid4()
        )
        assert found_run is None

    @pytest.mark.asyncio
    async def test_list_runs_for_wintern(self, test_session: AsyncSession, test_wintern):
        """Should list runs for a wintern with pagination."""
        # Create multiple runs
        for _ in range(5):
            await execution_service.create_run(test_session, test_wintern.id)

        runs, total = await execution_service.list_runs_for_wintern(
            test_session, test_wintern.id, skip=0, limit=3
        )

        assert len(runs) == 3
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_runs_for_wintern_empty(self, test_session: AsyncSession, test_wintern):
        """Should return empty list when no runs exist."""
        runs, total = await execution_service.list_runs_for_wintern(test_session, test_wintern.id)

        assert runs == []
        assert total == 0


class TestSeenContentDeduplication:
    """Tests for content deduplication operations."""

    @pytest.mark.asyncio
    async def test_get_seen_hashes_empty(self, test_session: AsyncSession, test_wintern):
        """Should return empty set when no content has been seen."""
        hashes = await execution_service.get_seen_hashes(test_session, test_wintern.id)

        assert hashes == set()

    @pytest.mark.asyncio
    async def test_record_and_get_seen_content(self, test_session: AsyncSession, test_wintern):
        """Should record and retrieve seen content hashes."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        url = "https://example.com/article"
        await execution_service.record_seen_content(
            test_session, test_wintern.id, run.id, url, "brave_search"
        )

        hashes = await execution_service.get_seen_hashes(test_session, test_wintern.id)
        expected_hash = execution_service.compute_content_hash(url)

        assert expected_hash in hashes

    @pytest.mark.asyncio
    async def test_record_seen_content_batch(self, test_session: AsyncSession, test_wintern):
        """Should record multiple pieces of content in a batch."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        items = [
            ("https://example.com/article1", "brave_search"),
            ("https://example.com/article2", "reddit"),
            ("https://example.com/article3", "brave_search"),
        ]
        inserted_count = await execution_service.record_seen_content_batch(
            test_session, test_wintern.id, run.id, items
        )

        assert inserted_count == 3

        hashes = await execution_service.get_seen_hashes(test_session, test_wintern.id)
        assert len(hashes) == 3

    @pytest.mark.asyncio
    async def test_record_seen_content_batch_handles_duplicates(
        self, test_session: AsyncSession, test_wintern
    ):
        """Should handle duplicate content gracefully with ON CONFLICT DO NOTHING."""
        run = await execution_service.create_run(test_session, test_wintern.id)

        # Insert some content
        items = [
            ("https://example.com/article1", "brave_search"),
            ("https://example.com/article2", "reddit"),
        ]
        inserted_count = await execution_service.record_seen_content_batch(
            test_session, test_wintern.id, run.id, items
        )
        assert inserted_count == 2

        # Try to insert duplicates - should not raise and should report fewer inserted
        duplicate_items = [
            ("https://example.com/article1", "brave_search"),  # duplicate
            ("https://example.com/article3", "brave_search"),  # new
        ]
        inserted_count = await execution_service.record_seen_content_batch(
            test_session, test_wintern.id, run.id, duplicate_items
        )
        # Only 1 new record should be inserted
        assert inserted_count == 1

        # Total should be 3 unique hashes
        hashes = await execution_service.get_seen_hashes(test_session, test_wintern.id)
        assert len(hashes) == 3


class TestSchedulingOperations:
    """Tests for scheduling-related operations."""

    def test_calculate_next_run_at(self):
        """Should calculate next run time from cron expression."""
        # 9am daily
        cron = "0 9 * * *"
        base = datetime(2024, 1, 15, 8, 0, 0, tzinfo=UTC)

        next_run = execution_service.calculate_next_run_at(cron, base)

        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run > base

    @pytest.mark.asyncio
    async def test_get_due_winterns_empty(self, test_session: AsyncSession):
        """Should return empty list when no winterns are due."""
        due = await execution_service.get_due_winterns(test_session)

        assert due == []

    @pytest.mark.asyncio
    async def test_get_due_winterns_returns_due(self, test_session: AsyncSession, test_wintern):
        """Should return winterns that are past their next_run_at."""
        # Set next_run_at to the past
        test_wintern.next_run_at = datetime.now(UTC) - timedelta(hours=1)
        await test_session.flush()

        due = await execution_service.get_due_winterns(test_session)

        assert len(due) == 1
        assert due[0].id == test_wintern.id

    @pytest.mark.asyncio
    async def test_get_due_winterns_excludes_inactive(
        self, test_session: AsyncSession, test_wintern
    ):
        """Should not return inactive winterns even if due."""
        test_wintern.next_run_at = datetime.now(UTC) - timedelta(hours=1)
        test_wintern.is_active = False
        await test_session.flush()

        due = await execution_service.get_due_winterns(test_session)

        assert due == []

    @pytest.mark.asyncio
    async def test_update_next_run_at(self, test_session: AsyncSession, test_wintern):
        """Should update next_run_at based on cron schedule."""
        old_next_run = test_wintern.next_run_at

        updated = await execution_service.update_next_run_at(test_session, test_wintern)

        assert updated.next_run_at is not None
        assert updated.next_run_at != old_next_run

    @pytest.mark.asyncio
    async def test_update_next_run_at_no_schedule(self, test_session: AsyncSession, test_user):
        """Should set next_run_at to None when no cron schedule."""
        wintern = Wintern(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="No Schedule",
            context="Test",
            cron_schedule=None,
            next_run_at=datetime.now(UTC),
        )
        test_session.add(wintern)
        await test_session.flush()

        updated = await execution_service.update_next_run_at(test_session, wintern)

        assert updated.next_run_at is None


class TestWinternLoading:
    """Tests for loading winterns for execution."""

    @pytest.mark.asyncio
    async def test_get_wintern_for_execution(
        self, test_session: AsyncSession, test_wintern_with_configs
    ):
        """Should load wintern with relationships."""
        wintern = await execution_service.get_wintern_for_execution(
            test_session, test_wintern_with_configs.id
        )

        assert wintern is not None
        assert wintern.id == test_wintern_with_configs.id
        # Relationships should be loaded
        assert len(wintern.source_configs) > 0
        assert len(wintern.delivery_configs) > 0

    @pytest.mark.asyncio
    async def test_get_wintern_for_execution_not_found(self, test_session: AsyncSession):
        """Should return None for non-existent wintern."""
        wintern = await execution_service.get_wintern_for_execution(test_session, uuid.uuid4())

        assert wintern is None

    @pytest.mark.asyncio
    async def test_get_wintern_for_execution_with_user_filter(
        self, test_session: AsyncSession, test_wintern, test_user
    ):
        """Should filter by user_id when provided."""
        # Should find with correct user_id
        wintern = await execution_service.get_wintern_for_execution(
            test_session, test_wintern.id, user_id=test_user.id
        )
        assert wintern is not None

        # Should not find with wrong user_id
        wintern = await execution_service.get_wintern_for_execution(
            test_session, test_wintern.id, user_id=uuid.uuid4()
        )
        assert wintern is None
