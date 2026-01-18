"""Tests for the execution executor - helper functions and orchestration."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.agents import CuratedContent, InterpretedContext, ScoredItem
from wintern.agents.composer import DeliveryChannel as AgentDeliveryChannel
from wintern.delivery.schemas import DeliveryItem
from wintern.execution.executor import (
    ExecutionError,
    NoDeliveryConfiguredError,
    NoSourcesConfiguredError,
    delivery_type_to_agent_channel,
    execute_wintern,
    scored_item_to_delivery_item,
    search_result_to_scraped_item,
)
from wintern.sources.schemas import SearchResult
from wintern.winterns.models import DeliveryConfig, DeliveryType, SourceConfig, SourceType, Wintern


class TestScoredItemToDeliveryItem:
    """Tests for scored_item_to_delivery_item helper."""

    def test_converts_all_fields(self):
        """Should convert all ScoredItem fields to DeliveryItem."""
        scored = ScoredItem(
            url="https://example.com",
            title="Test Article",
            relevance_score=85,
            reasoning="Highly relevant to the topic",
            key_excerpt="This is the key excerpt",
        )

        delivery = scored_item_to_delivery_item(scored)

        assert isinstance(delivery, DeliveryItem)
        assert delivery.url == "https://example.com"
        assert delivery.title == "Test Article"
        assert delivery.relevance_score == 85
        assert delivery.reasoning == "Highly relevant to the topic"
        assert delivery.key_excerpt == "This is the key excerpt"

    def test_handles_none_key_excerpt(self):
        """Should handle ScoredItem without key_excerpt."""
        scored = ScoredItem(
            url="https://example.com",
            title="Test Article",
            relevance_score=65,
            reasoning="Moderately relevant",
            key_excerpt=None,
        )

        delivery = scored_item_to_delivery_item(scored)

        assert delivery.key_excerpt is None


class TestDeliveryTypeToAgentChannel:
    """Tests for delivery_type_to_agent_channel helper."""

    def test_slack_conversion(self):
        """Should convert SLACK to AgentDeliveryChannel.SLACK."""
        result = delivery_type_to_agent_channel(DeliveryType.SLACK)
        assert result == AgentDeliveryChannel.SLACK

    def test_email_conversion(self):
        """Should convert EMAIL to AgentDeliveryChannel.EMAIL."""
        result = delivery_type_to_agent_channel(DeliveryType.EMAIL)
        assert result == AgentDeliveryChannel.EMAIL

    def test_sms_conversion(self):
        """Should convert SMS to AgentDeliveryChannel.SMS."""
        result = delivery_type_to_agent_channel(DeliveryType.SMS)
        assert result == AgentDeliveryChannel.SMS


class TestSearchResultToScrapedItem:
    """Tests for search_result_to_scraped_item helper."""

    def test_converts_all_fields(self):
        """Should convert SearchResult to ScrapedItem."""
        result = SearchResult(
            url="https://example.com/article",
            title="Test Article",
            snippet="This is a test snippet",
            source="brave_search",
            published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            metadata={"extra": "data"},
        )

        scraped = search_result_to_scraped_item(result)

        assert scraped.url == "https://example.com/article"
        assert scraped.title == "Test Article"
        assert scraped.snippet == "This is a test snippet"
        assert scraped.source == "brave_search"
        assert scraped.published_date == "2024-01-15T12:00:00+00:00"

    def test_handles_none_published_at(self):
        """Should handle SearchResult without published_at."""
        result = SearchResult(
            url="https://example.com/article",
            title="Test Article",
            snippet="This is a test snippet",
            source="reddit",
            published_at=None,
            metadata={},
        )

        scraped = search_result_to_scraped_item(result)

        assert scraped.published_date is None


class TestExecutionErrors:
    """Tests for execution exception classes."""

    def test_no_sources_configured_error(self):
        """NoSourcesConfiguredError should include wintern_id."""
        wintern_id = uuid.uuid4()
        error = NoSourcesConfiguredError(wintern_id)

        assert error.wintern_id == wintern_id
        assert str(wintern_id) in str(error)
        assert "sources" in str(error).lower()

    def test_no_delivery_configured_error(self):
        """NoDeliveryConfiguredError should include wintern_id."""
        wintern_id = uuid.uuid4()
        error = NoDeliveryConfiguredError(wintern_id)

        assert error.wintern_id == wintern_id
        assert str(wintern_id) in str(error)
        assert "delivery" in str(error).lower()


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
async def test_wintern_full(test_session: AsyncSession, test_user):
    """Create a test wintern with active source and delivery configs."""
    wintern = Wintern(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Full Test Wintern",
        context="I want to track AI developments and news",
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


class TestExecuteWintern:
    """Tests for the main execute_wintern function."""

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_wintern(self, test_session: AsyncSession):
        """Should raise ExecutionError when wintern not found."""
        fake_id = uuid.uuid4()

        with pytest.raises(ExecutionError) as exc_info:
            await execute_wintern(test_session, fake_id)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_error_for_no_sources(
        self, test_session: AsyncSession, test_user
    ):
        """Should raise NoSourcesConfiguredError when no active sources."""
        wintern = Wintern(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="No Sources",
            context="Test",
            is_active=True,
        )
        test_session.add(wintern)

        # Add a delivery config but no sources
        delivery = DeliveryConfig(
            wintern_id=wintern.id,
            delivery_type=DeliveryType.SLACK,
            config={},
            is_active=True,
        )
        test_session.add(delivery)
        await test_session.flush()

        with pytest.raises(NoSourcesConfiguredError):
            await execute_wintern(test_session, wintern.id)

    @pytest.mark.asyncio
    async def test_raises_error_for_no_delivery(
        self, test_session: AsyncSession, test_user
    ):
        """Should raise NoDeliveryConfiguredError when no active delivery channels."""
        wintern = Wintern(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="No Delivery",
            context="Test",
            is_active=True,
        )
        test_session.add(wintern)

        # Add a source config but no delivery
        source = SourceConfig(
            wintern_id=wintern.id,
            source_type=SourceType.BRAVE_SEARCH,
            config={},
            is_active=True,
        )
        test_session.add(source)
        await test_session.flush()

        with pytest.raises(NoDeliveryConfiguredError):
            await execute_wintern(test_session, wintern.id)

    @pytest.mark.asyncio
    async def test_creates_run_record(
        self, test_session: AsyncSession, test_wintern_full
    ):
        """Should create a WinternRun record even if execution fails later."""
        from wintern.execution.models import WinternRun

        # Mock interpret_context to raise an error
        with patch(
            "wintern.execution.executor.interpret_context",
            side_effect=Exception("Interpreter failed"),
        ):
            with pytest.raises(ExecutionError):
                await execute_wintern(test_session, test_wintern_full.id)

        # Check that a run record was created and marked as failed
        from sqlalchemy import select

        stmt = select(WinternRun).where(WinternRun.wintern_id == test_wintern_full.id)
        result = await test_session.execute(stmt)
        run = result.scalar_one_or_none()

        assert run is not None
        assert run.error_message is not None

    @pytest.mark.asyncio
    async def test_full_execution_flow_mocked(
        self, test_session: AsyncSession, test_wintern_full
    ):
        """Should complete full execution flow with mocked agents and sources."""
        # Mock interpreted context
        mock_interpreted = InterpretedContext(
            search_queries=["AI news 2024"],
            relevance_signals=["artificial intelligence"],
            exclusion_criteria=[],
            entity_focus=["OpenAI"],
        )
        mock_interpret_result = MagicMock()
        mock_interpret_result.output = mock_interpreted

        # Mock search results
        mock_search_results = [
            SearchResult(
                url="https://example.com/article1",
                title="AI Article 1",
                snippet="Test snippet 1",
                source="brave_search",
                published_at=datetime.now(UTC),
                metadata={},
            ),
            SearchResult(
                url="https://example.com/article2",
                title="AI Article 2",
                snippet="Test snippet 2",
                source="brave_search",
                published_at=datetime.now(UTC),
                metadata={},
            ),
        ]

        # Mock curated content
        mock_curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com/article1",
                    title="AI Article 1",
                    relevance_score=85,
                    reasoning="Highly relevant",
                    key_excerpt="Key point from article",
                ),
            ],
            summary="Found 1 relevant article about AI",
        )
        mock_curate_result = MagicMock()
        mock_curate_result.output = mock_curated

        # Mock digest content
        mock_digest = MagicMock()
        mock_digest.subject = "AI News Digest"
        mock_digest.body_slack = "Test digest body"
        mock_digest.body_plain = "Plain text body"
        mock_digest.item_count = 1
        mock_compose_result = MagicMock()
        mock_compose_result.output = mock_digest

        # Mock delivery result
        mock_delivery_result = MagicMock()
        mock_delivery_result.channel = "slack"
        mock_delivery_result.success = True
        mock_delivery_result.error_message = None

        with (
            patch(
                "wintern.execution.executor.interpret_context",
                return_value=mock_interpret_result,
            ),
            patch(
                "wintern.execution.executor.curate_content",
                return_value=mock_curate_result,
            ),
            patch(
                "wintern.execution.executor.compose_digest",
                return_value=mock_compose_result,
            ),
            patch(
                "wintern.execution.executor.create_data_source"
            ) as mock_create_source,
            patch(
                "wintern.execution.executor.create_delivery_channel"
            ) as mock_create_delivery,
        ):
            # Setup source mock
            mock_source = AsyncMock()
            mock_source.source_name = "brave_search"
            mock_source.search.return_value = mock_search_results
            mock_create_source.return_value = mock_source

            # Setup delivery mock
            mock_channel = AsyncMock()
            mock_channel.deliver.return_value = mock_delivery_result
            mock_create_delivery.return_value = mock_channel

            run_id = await execute_wintern(test_session, test_wintern_full.id)

        assert run_id is not None

        # Verify run completed successfully
        from sqlalchemy import select

        from wintern.execution.models import RunStatus, WinternRun

        stmt = select(WinternRun).where(WinternRun.id == run_id)
        result = await test_session.execute(stmt)
        run = result.scalar_one()

        assert run.status == RunStatus.COMPLETED
        assert run.digest_content is not None
        assert run.metadata_ is not None
        assert run.metadata_["curated"] == 1
