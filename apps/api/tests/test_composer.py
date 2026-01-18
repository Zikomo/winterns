"""Tests for the digest composer agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from wintern.agents.composer import (
    ComposerInput,
    DeliveryChannel,
    DigestContent,
    UserContext,
    compose_digest,
    create_composer_agent,
    format_composer_input,
)
from wintern.agents.curator import CuratedContent, ScoredItem

# -----------------------------------------------------------------------------
# Input Model Tests
# -----------------------------------------------------------------------------


class TestDeliveryChannel:
    """Tests for the DeliveryChannel enum."""

    def test_enum_values(self):
        """Test that expected enum values exist."""
        assert DeliveryChannel.EMAIL == "email"
        assert DeliveryChannel.SLACK == "slack"
        assert DeliveryChannel.SMS == "sms"

    def test_all_channels(self):
        """Test that we have exactly 3 delivery channels."""
        channels = list(DeliveryChannel)
        assert len(channels) == 3


class TestUserContext:
    """Tests for the UserContext model."""

    def test_empty_user_context(self):
        """Test creating user context with no fields."""
        ctx = UserContext()
        assert ctx.name is None
        assert ctx.preferences is None
        assert ctx.timezone is None

    def test_full_user_context(self):
        """Test creating user context with all fields."""
        ctx = UserContext(
            name="Alice",
            preferences="Prefers technical depth over breadth",
            timezone="America/New_York",
        )
        assert ctx.name == "Alice"
        assert ctx.preferences == "Prefers technical depth over breadth"
        assert ctx.timezone == "America/New_York"

    def test_partial_user_context(self):
        """Test creating user context with some fields."""
        ctx = UserContext(name="Bob")
        assert ctx.name == "Bob"
        assert ctx.preferences is None
        assert ctx.timezone is None


class TestComposerInput:
    """Tests for the ComposerInput model."""

    def test_minimal_composer_input(self):
        """Test creating composer input with required fields only."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com",
                    title="Test Article",
                    relevance_score=85,
                    reasoning="Highly relevant.",
                )
            ],
            summary="Found one relevant article.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
        )
        assert input_data.curated_content == curated
        assert input_data.channel == DeliveryChannel.EMAIL
        assert input_data.user_context.name is None  # Default UserContext
        assert input_data.research_topic is None

    def test_full_composer_input(self):
        """Test creating composer input with all fields."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com",
                    title="Test Article",
                    relevance_score=85,
                    reasoning="Highly relevant.",
                )
            ],
            summary="Found one relevant article.",
        )
        user_ctx = UserContext(
            name="Alice",
            preferences="Technical focus",
            timezone="UTC",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SLACK,
            user_context=user_ctx,
            research_topic="AI developments in 2024",
        )
        assert input_data.channel == DeliveryChannel.SLACK
        assert input_data.user_context.name == "Alice"
        assert input_data.research_topic == "AI developments in 2024"

    def test_composer_input_requires_curated_content(self):
        """Test that curated_content is required."""
        with pytest.raises(ValidationError, match="curated_content"):
            ComposerInput(channel=DeliveryChannel.EMAIL)  # type: ignore

    def test_composer_input_requires_channel(self):
        """Test that channel is required."""
        curated = CuratedContent(items=[], summary="No items.")
        with pytest.raises(ValidationError, match="channel"):
            ComposerInput(curated_content=curated)  # type: ignore

    def test_composer_input_all_channels(self):
        """Test composer input works with all delivery channels."""
        curated = CuratedContent(items=[], summary="No items.")
        for channel in DeliveryChannel:
            input_data = ComposerInput(curated_content=curated, channel=channel)
            assert input_data.channel == channel


# -----------------------------------------------------------------------------
# Output Model Tests
# -----------------------------------------------------------------------------


class TestDigestContent:
    """Tests for the DigestContent output model."""

    def test_valid_digest_content(self):
        """Test creating valid digest content."""
        content = DigestContent(
            subject="Your AI Research Digest",
            body_html="<h1>Digest</h1><p>Content here...</p>",
            body_plain="Digest\n\nContent here...",
            body_slack="*Digest*\n\nContent here...",
            item_count=3,
        )
        assert content.subject == "Your AI Research Digest"
        assert "<h1>" in content.body_html
        assert content.item_count == 3

    def test_subject_max_length(self):
        """Test that subject cannot exceed 100 characters."""
        long_subject = "x" * 101
        with pytest.raises(ValidationError, match="at most 100 characters"):
            DigestContent(
                subject=long_subject,
                body_html="<p>HTML</p>",
                body_plain="Plain",
                body_slack="Slack",
                item_count=1,
            )

    def test_subject_at_max_length(self):
        """Test that subject accepts exactly 100 characters."""
        subject_100 = "x" * 100
        content = DigestContent(
            subject=subject_100,
            body_html="<p>HTML</p>",
            body_plain="Plain",
            body_slack="Slack",
            item_count=1,
        )
        assert len(content.subject) == 100

    def test_item_count_minimum(self):
        """Test that item_count must be at least 0."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DigestContent(
                subject="Test",
                body_html="<p>HTML</p>",
                body_plain="Plain",
                body_slack="Slack",
                item_count=-1,
            )

    def test_item_count_zero(self):
        """Test that item_count can be 0."""
        content = DigestContent(
            subject="No Items Found",
            body_html="<p>No relevant items.</p>",
            body_plain="No relevant items.",
            body_slack="No relevant items.",
            item_count=0,
        )
        assert content.item_count == 0

    def test_digest_content_requires_all_body_formats(self):
        """Test that all body formats are required."""
        with pytest.raises(ValidationError, match="body_html"):
            DigestContent(
                subject="Test",
                body_plain="Plain",
                body_slack="Slack",
                item_count=1,
            )  # type: ignore

        with pytest.raises(ValidationError, match="body_plain"):
            DigestContent(
                subject="Test",
                body_html="<p>HTML</p>",
                body_slack="Slack",
                item_count=1,
            )  # type: ignore

        with pytest.raises(ValidationError, match="body_slack"):
            DigestContent(
                subject="Test",
                body_html="<p>HTML</p>",
                body_plain="Plain",
                item_count=1,
            )  # type: ignore


# -----------------------------------------------------------------------------
# Format Input Tests
# -----------------------------------------------------------------------------


class TestFormatComposerInput:
    """Tests for the format_composer_input function."""

    def test_format_basic_input(self):
        """Test formatting basic composer input."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com/article",
                    title="AI Funding News",
                    relevance_score=85,
                    reasoning="Directly relevant to AI funding topic.",
                )
            ],
            summary="Found 1 highly relevant article.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
        )
        result = format_composer_input(input_data)

        assert "## Delivery Channel" in result
        assert "EMAIL" in result
        assert "## Content Summary" in result
        assert "Found 1 highly relevant article." in result
        assert "## Curated Items (1 total)" in result
        assert "### Item 1 (Score: 85/100)" in result
        assert "**Title**: AI Funding News" in result
        assert "**URL**: https://example.com/article" in result
        assert "**Why relevant**: Directly relevant to AI funding topic." in result

    def test_format_with_research_topic(self):
        """Test formatting input with research topic."""
        curated = CuratedContent(items=[], summary="No items.")
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SLACK,
            research_topic="AI developments in healthcare",
        )
        result = format_composer_input(input_data)

        assert "## Research Topic" in result
        assert "AI developments in healthcare" in result

    def test_format_with_user_context(self):
        """Test formatting input with user context."""
        curated = CuratedContent(items=[], summary="No items.")
        user_ctx = UserContext(
            name="Alice",
            preferences="Technical details preferred",
            timezone="America/Los_Angeles",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
            user_context=user_ctx,
        )
        result = format_composer_input(input_data)

        assert "## User Context" in result
        assert "**Name**: Alice" in result
        assert "**Preferences**: Technical details preferred" in result
        assert "**Timezone**: America/Los_Angeles" in result

    def test_format_omits_empty_user_context(self):
        """Test that empty user context is omitted from formatting."""
        curated = CuratedContent(items=[], summary="No items.")
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SMS,
            user_context=UserContext(),  # All None
        )
        result = format_composer_input(input_data)

        assert "## User Context" not in result

    def test_format_with_key_excerpt(self):
        """Test formatting item with key excerpt."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com",
                    title="Test Article",
                    relevance_score=90,
                    reasoning="Excellent match.",
                    key_excerpt="This is the key finding from the article.",
                )
            ],
            summary="Found excellent match.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
        )
        result = format_composer_input(input_data)

        assert '**Key excerpt**: "This is the key finding from the article."' in result

    def test_format_multiple_items(self):
        """Test formatting with multiple curated items."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example1.com",
                    title="Article 1",
                    relevance_score=95,
                    reasoning="Top match.",
                ),
                ScoredItem(
                    url="https://example2.com",
                    title="Article 2",
                    relevance_score=80,
                    reasoning="Good match.",
                ),
                ScoredItem(
                    url="https://example3.com",
                    title="Article 3",
                    relevance_score=65,
                    reasoning="Moderate match.",
                ),
            ],
            summary="Found 3 relevant articles.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SLACK,
        )
        result = format_composer_input(input_data)

        assert "## Curated Items (3 total)" in result
        assert "### Item 1 (Score: 95/100)" in result
        assert "### Item 2 (Score: 80/100)" in result
        assert "### Item 3 (Score: 65/100)" in result

    def test_format_all_channels(self):
        """Test formatting for all delivery channels."""
        curated = CuratedContent(items=[], summary="No items.")
        for channel in DeliveryChannel:
            input_data = ComposerInput(
                curated_content=curated,
                channel=channel,
            )
            result = format_composer_input(input_data)
            assert channel.value.upper() in result


# -----------------------------------------------------------------------------
# Agent Tests (with mocking)
# -----------------------------------------------------------------------------


class TestCreateComposerAgent:
    """Tests for the create_composer_agent function."""

    def test_creates_agent_with_default_model(self):
        """Test that agent is created with default model from settings."""
        with (
            patch("wintern.agents.composer.settings") as mock_settings,
            patch("wintern.agents.composer.Agent") as mock_agent_class,
        ):
            mock_settings.default_model = "anthropic/claude-sonnet-4-20250514"
            mock_agent_class.return_value = MagicMock()

            agent = create_composer_agent()

            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:anthropic/claude-sonnet-4-20250514"
            assert agent is not None

    def test_creates_agent_with_custom_model(self):
        """Test that agent can be created with a custom model."""
        with patch("wintern.agents.composer.Agent") as mock_agent_class:
            mock_agent_class.return_value = MagicMock()

            agent = create_composer_agent(model="openai/gpt-4")

            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:openai/gpt-4"
            assert agent is not None


class TestComposeDigest:
    """Tests for the compose_digest function."""

    @pytest.mark.asyncio
    async def test_compose_digest_success(self):
        """Test successful digest composition with mocked agent."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com/ai-news",
                    title="Major AI Breakthrough",
                    relevance_score=92,
                    reasoning="Directly covers AI advancements.",
                    key_excerpt="Researchers achieved a 50% improvement...",
                )
            ],
            summary="Found 1 highly relevant AI news article.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
            user_context=UserContext(name="Alice"),
            research_topic="AI breakthroughs 2024",
        )

        mock_result_data = DigestContent(
            subject="AI Research Digest: Major Breakthrough Discovered",
            body_html="<h1>Hi Alice!</h1><p>Here's your digest...</p>",
            body_plain="Hi Alice!\n\nHere's your digest...",
            body_slack="*Hi Alice!*\n\nHere's your digest...",
            item_count=1,
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.composer.get_digest_composer", return_value=mock_agent):
            result = await compose_digest(input_data)

            mock_agent.run.assert_called_once()
            assert result.output.subject == mock_result_data.subject
            assert result.output.item_count == 1
            assert "Alice" in result.output.body_html

    @pytest.mark.asyncio
    async def test_compose_digest_with_custom_model(self):
        """Test digest composition with a custom model."""
        curated = CuratedContent(items=[], summary="No items.")
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SLACK,
        )

        mock_result_data = DigestContent(
            subject="No New Items",
            body_html="<p>No relevant items found.</p>",
            body_plain="No relevant items found.",
            body_slack="No relevant items found.",
            item_count=0,
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        with patch("wintern.agents.composer.create_composer_agent") as mock_create:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_create.return_value = mock_agent

            result = await compose_digest(input_data, model="openai/gpt-4")

            mock_create.assert_called_once_with("openai/gpt-4")
            assert result.output == mock_result_data

    @pytest.mark.asyncio
    async def test_compose_digest_formats_input_correctly(self):
        """Test that input is formatted correctly before being sent to agent."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com",
                    title="Test Article",
                    relevance_score=75,
                    reasoning="Good match.",
                )
            ],
            summary="Found 1 article.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SMS,
            user_context=UserContext(name="Bob", timezone="UTC"),
            research_topic="Tech news",
        )

        mock_result_data = DigestContent(
            subject="Tech Update",
            body_html="<p>Brief</p>",
            body_plain="Brief update.",
            body_slack="Brief update.",
            item_count=1,
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.composer.get_digest_composer", return_value=mock_agent):
            await compose_digest(input_data)

            call_args = mock_agent.run.call_args
            prompt = call_args[0][0]

            assert "## Research Topic" in prompt
            assert "Tech news" in prompt
            assert "SMS" in prompt
            assert "**Name**: Bob" in prompt
            assert "**Timezone**: UTC" in prompt
            assert "### Item 1 (Score: 75/100)" in prompt


# -----------------------------------------------------------------------------
# Integration-style Tests
# -----------------------------------------------------------------------------


class TestComposerIntegration:
    """Integration-style tests for the composer module."""

    def test_full_input_output_cycle(self):
        """Test creating input, formatting, and validating output."""
        # Create realistic curated content
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://techcrunch.com/2024/01/15/ai-funding",
                    title="AI Startup Raises $100M Series B",
                    relevance_score=92,
                    reasoning="Direct match for AI funding tracking.",
                    key_excerpt="The startup raised $100M to expand AI research.",
                ),
                ScoredItem(
                    url="https://reuters.com/tech/ai-investment",
                    title="VC Investment in AI Hits Record",
                    relevance_score=88,
                    reasoning="Covers broader AI investment trends.",
                    key_excerpt="Total AI investment reached $50B in 2024.",
                ),
                ScoredItem(
                    url="https://wired.com/ai-future",
                    title="The Future of AI in Enterprise",
                    relevance_score=72,
                    reasoning="Discusses AI adoption in enterprises.",
                ),
            ],
            summary="Found 3 relevant articles covering AI funding and investment trends.",
        )

        user_ctx = UserContext(
            name="Alice Chen",
            preferences="Focus on Series A+ funding rounds",
            timezone="America/New_York",
        )

        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.EMAIL,
            user_context=user_ctx,
            research_topic="AI startup funding and investment trends",
        )

        # Format and verify
        formatted = format_composer_input(input_data)

        assert "AI startup funding and investment trends" in formatted
        assert "EMAIL" in formatted
        assert "Alice Chen" in formatted
        assert "Focus on Series A+ funding rounds" in formatted
        assert "America/New_York" in formatted
        assert "## Curated Items (3 total)" in formatted
        assert "Score: 92/100" in formatted
        assert "Score: 88/100" in formatted
        assert "Score: 72/100" in formatted

        # Create valid output
        output = DigestContent(
            subject="AI Funding Digest: $100M Raise + Record Investment",
            body_html="""
            <h1>Hi Alice!</h1>
            <p>Here are today's top AI funding stories:</p>
            <h2>1. AI Startup Raises $100M Series B</h2>
            <p><a href="https://techcrunch.com/2024/01/15/ai-funding">Read more</a></p>
            <blockquote>The startup raised $100M to expand AI research.</blockquote>
            """,
            body_plain="""
Hi Alice!

Here are today's top AI funding stories:

1. AI Startup Raises $100M Series B
https://techcrunch.com/2024/01/15/ai-funding
"The startup raised $100M to expand AI research."

2. VC Investment in AI Hits Record
https://reuters.com/tech/ai-investment
            """,
            body_slack="""
*Hi Alice!* :wave:

Here are today's top AI funding stories:

• *AI Startup Raises $100M Series B*
  <https://techcrunch.com/2024/01/15/ai-funding|Read more>
  > The startup raised $100M to expand AI research.

• *VC Investment in AI Hits Record*
  <https://reuters.com/tech/ai-investment|Read more>
            """,
            item_count=3,
        )

        # Verify output
        assert len(output.subject) <= 100
        assert output.item_count == 3
        assert "Alice" in output.body_html
        assert "Alice" in output.body_plain
        assert "Alice" in output.body_slack
        assert "<a href=" in output.body_html  # HTML links
        assert "https://" in output.body_plain  # Plain URLs
        assert "<https://" in output.body_slack  # Slack link format

    def test_sms_channel_formatting(self):
        """Test that SMS channel input is properly formatted."""
        curated = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com",
                    title="Breaking News",
                    relevance_score=95,
                    reasoning="Critical update.",
                )
            ],
            summary="1 critical item.",
        )
        input_data = ComposerInput(
            curated_content=curated,
            channel=DeliveryChannel.SMS,
        )
        formatted = format_composer_input(input_data)

        assert "SMS" in formatted
        # SMS formatting should still include all details for the agent
        # The agent decides how to condense for SMS
        assert "### Item 1" in formatted
