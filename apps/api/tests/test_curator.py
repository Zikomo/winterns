"""Tests for the content curator agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from wintern.agents.curator import (
    CuratedContent,
    CuratorInput,
    ScoredItem,
    ScrapedItem,
    create_curator_agent,
    curate_content,
    format_curator_input,
)
from wintern.agents.interpreter import InterpretedContext

# -----------------------------------------------------------------------------
# Input Model Tests
# -----------------------------------------------------------------------------


class TestScrapedItem:
    """Tests for the ScrapedItem model."""

    def test_minimal_scraped_item(self):
        """Test creating a scraped item with required fields only."""
        item = ScrapedItem(
            url="https://example.com/article",
            title="Example Article",
            snippet="This is a snippet of the article content.",
        )
        assert item.url == "https://example.com/article"
        assert item.title == "Example Article"
        assert item.snippet == "This is a snippet of the article content."
        assert item.source is None
        assert item.published_date is None

    def test_full_scraped_item(self):
        """Test creating a scraped item with all fields."""
        item = ScrapedItem(
            url="https://techcrunch.com/2024/01/15/ai-funding",
            title="AI Startup Raises $50M",
            snippet="A promising AI startup has raised a significant funding round...",
            source="techcrunch.com",
            published_date="2024-01-15",
        )
        assert item.source == "techcrunch.com"
        assert item.published_date == "2024-01-15"

    def test_scraped_item_url_required(self):
        """Test that url field is required."""
        with pytest.raises(ValidationError, match="url"):
            ScrapedItem(title="Title", snippet="Snippet")  # type: ignore

    def test_scraped_item_title_required(self):
        """Test that title field is required."""
        with pytest.raises(ValidationError, match="title"):
            ScrapedItem(url="https://example.com", snippet="Snippet")  # type: ignore

    def test_scraped_item_snippet_required(self):
        """Test that snippet field is required."""
        with pytest.raises(ValidationError, match="snippet"):
            ScrapedItem(url="https://example.com", title="Title")  # type: ignore


class TestCuratorInput:
    """Tests for the CuratorInput model."""

    def test_valid_curator_input(self):
        """Test creating valid curator input."""
        context = InterpretedContext(
            search_queries=["AI funding 2024"],
            relevance_signals=["Series A", "funding round"],
        )
        items = [
            ScrapedItem(
                url="https://example.com",
                title="Test Article",
                snippet="Test snippet",
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        assert input_data.interpreted_context == context
        assert len(input_data.items) == 1

    def test_curator_input_requires_items(self):
        """Test that items list cannot be empty."""
        context = InterpretedContext(
            search_queries=["query"],
            relevance_signals=["signal"],
        )
        with pytest.raises(ValidationError, match="at least 1 item"):
            CuratorInput(interpreted_context=context, items=[])

    def test_curator_input_requires_context(self):
        """Test that interpreted_context is required."""
        items = [
            ScrapedItem(
                url="https://example.com",
                title="Test",
                snippet="Test",
            )
        ]
        with pytest.raises(ValidationError, match="interpreted_context"):
            CuratorInput(items=items)  # type: ignore


# -----------------------------------------------------------------------------
# Output Model Tests
# -----------------------------------------------------------------------------


class TestScoredItem:
    """Tests for the ScoredItem model."""

    def test_minimal_scored_item(self):
        """Test creating a scored item with required fields only."""
        item = ScoredItem(
            url="https://example.com/article",
            title="Test Article",
            relevance_score=75,
            reasoning="Highly relevant due to topic match.",
        )
        assert item.url == "https://example.com/article"
        assert item.title == "Test Article"
        assert item.relevance_score == 75
        assert item.reasoning == "Highly relevant due to topic match."
        assert item.key_excerpt is None

    def test_scored_item_with_excerpt(self):
        """Test creating a scored item with key excerpt."""
        item = ScoredItem(
            url="https://example.com/article",
            title="Test Article",
            relevance_score=85,
            reasoning="Contains key funding information.",
            key_excerpt="The company raised $50M in Series B funding.",
        )
        assert item.key_excerpt == "The company raised $50M in Series B funding."

    def test_relevance_score_minimum(self):
        """Test that relevance_score must be at least 0."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ScoredItem(
                url="https://example.com",
                title="Test",
                relevance_score=-1,
                reasoning="Test reasoning",
            )

    def test_relevance_score_maximum(self):
        """Test that relevance_score cannot exceed 100."""
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            ScoredItem(
                url="https://example.com",
                title="Test",
                relevance_score=101,
                reasoning="Test reasoning",
            )

    def test_relevance_score_boundaries(self):
        """Test that relevance_score accepts boundary values."""
        item_zero = ScoredItem(
            url="https://example.com",
            title="Test",
            relevance_score=0,
            reasoning="Not relevant at all.",
        )
        assert item_zero.relevance_score == 0

        item_hundred = ScoredItem(
            url="https://example.com",
            title="Test",
            relevance_score=100,
            reasoning="Perfectly relevant.",
        )
        assert item_hundred.relevance_score == 100

    def test_reasoning_max_length(self):
        """Test that reasoning cannot exceed 200 characters."""
        long_reasoning = "x" * 201
        with pytest.raises(ValidationError, match="at most 200 characters"):
            ScoredItem(
                url="https://example.com",
                title="Test",
                relevance_score=50,
                reasoning=long_reasoning,
            )

    def test_reasoning_at_max_length(self):
        """Test that reasoning accepts exactly 200 characters."""
        reasoning_200 = "x" * 200
        item = ScoredItem(
            url="https://example.com",
            title="Test",
            relevance_score=50,
            reasoning=reasoning_200,
        )
        assert len(item.reasoning) == 200


class TestCuratedContent:
    """Tests for the CuratedContent model."""

    def test_valid_curated_content(self):
        """Test creating valid curated content."""
        items = [
            ScoredItem(
                url="https://example.com",
                title="Test Article",
                relevance_score=80,
                reasoning="Highly relevant.",
            )
        ]
        content = CuratedContent(
            items=items,
            summary="Found one highly relevant article about the topic.",
        )
        assert len(content.items) == 1
        assert "highly relevant" in content.summary

    def test_curated_content_empty_items(self):
        """Test that curated content allows empty items list."""
        content = CuratedContent(
            items=[],
            summary="No relevant content found matching the criteria.",
        )
        assert len(content.items) == 0

    def test_curated_content_requires_summary(self):
        """Test that summary is required."""
        with pytest.raises(ValidationError, match="summary"):
            CuratedContent(items=[])  # type: ignore


# -----------------------------------------------------------------------------
# Format Input Tests
# -----------------------------------------------------------------------------


class TestFormatCuratorInput:
    """Tests for the format_curator_input function."""

    def test_format_basic_input(self):
        """Test formatting basic curator input."""
        context = InterpretedContext(
            search_queries=["AI funding 2024"],
            relevance_signals=["funding round", "Series A"],
        )
        items = [
            ScrapedItem(
                url="https://example.com/article",
                title="AI Startup Funding",
                snippet="A new AI startup raised funding...",
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        result = format_curator_input(input_data)

        assert "## Interpreted Research Context" in result
        assert "### Search Queries" in result
        assert "- AI funding 2024" in result
        assert "### Relevance Signals" in result
        assert "- funding round" in result
        assert "## Content Items to Evaluate" in result
        assert "### Item 1" in result
        assert "**Title**: AI Startup Funding" in result
        assert "**URL**: https://example.com/article" in result
        assert "**Snippet**: A new AI startup raised funding..." in result

    def test_format_with_exclusion_criteria(self):
        """Test formatting input with exclusion criteria."""
        context = InterpretedContext(
            search_queries=["AI news"],
            relevance_signals=["artificial intelligence"],
            exclusion_criteria=["promotional content", "paywalled"],
        )
        items = [
            ScrapedItem(
                url="https://example.com",
                title="Test",
                snippet="Test snippet",
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        result = format_curator_input(input_data)

        assert "### Exclusion Criteria" in result
        assert "- promotional content" in result
        assert "- paywalled" in result

    def test_format_with_entity_focus(self):
        """Test formatting input with entity focus."""
        context = InterpretedContext(
            search_queries=["AI company news"],
            relevance_signals=["announcement"],
            entity_focus=["OpenAI", "Anthropic", "Google"],
        )
        items = [
            ScrapedItem(
                url="https://example.com",
                title="Test",
                snippet="Test snippet",
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        result = format_curator_input(input_data)

        assert "### Entities to Track" in result
        assert "- OpenAI" in result
        assert "- Anthropic" in result
        assert "- Google" in result

    def test_format_multiple_items(self):
        """Test formatting with multiple scraped items."""
        context = InterpretedContext(
            search_queries=["query"],
            relevance_signals=["signal"],
        )
        items = [
            ScrapedItem(
                url="https://example1.com",
                title="Article 1",
                snippet="Snippet 1",
                source="example1.com",
            ),
            ScrapedItem(
                url="https://example2.com",
                title="Article 2",
                snippet="Snippet 2",
                published_date="2024-01-15",
            ),
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        result = format_curator_input(input_data)

        assert "### Item 1" in result
        assert "### Item 2" in result
        assert "**Source**: example1.com" in result
        assert "**Published**: 2024-01-15" in result

    def test_format_omits_empty_optional_fields(self):
        """Test that empty optional fields are omitted from formatting."""
        context = InterpretedContext(
            search_queries=["query"],
            relevance_signals=["signal"],
            exclusion_criteria=[],  # Empty
            entity_focus=[],  # Empty
        )
        items = [
            ScrapedItem(
                url="https://example.com",
                title="Test",
                snippet="Snippet",
                source=None,  # Empty
                published_date=None,  # Empty
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)
        result = format_curator_input(input_data)

        assert "### Exclusion Criteria" not in result
        assert "### Entities to Track" not in result
        assert "**Source**:" not in result
        assert "**Published**:" not in result


# -----------------------------------------------------------------------------
# Agent Tests (with mocking)
# -----------------------------------------------------------------------------


class TestCreateCuratorAgent:
    """Tests for the create_curator_agent function."""

    def test_creates_agent_with_default_model(self):
        """Test that agent is created with default model from settings."""
        with (
            patch("wintern.agents.curator.settings") as mock_settings,
            patch("wintern.agents.curator.Agent") as mock_agent_class,
        ):
            mock_settings.default_model = "anthropic/claude-sonnet-4-20250514"
            mock_agent_class.return_value = MagicMock()

            agent = create_curator_agent()

            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:anthropic/claude-sonnet-4-20250514"
            assert agent is not None

    def test_creates_agent_with_custom_model(self):
        """Test that agent can be created with a custom model."""
        with patch("wintern.agents.curator.Agent") as mock_agent_class:
            mock_agent_class.return_value = MagicMock()

            agent = create_curator_agent(model="openai/gpt-4")

            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:openai/gpt-4"
            assert agent is not None


class TestCurateContent:
    """Tests for the curate_content function."""

    @pytest.mark.asyncio
    async def test_curate_content_success(self):
        """Test successful content curation with mocked agent."""
        context = InterpretedContext(
            search_queries=["AI funding 2024"],
            relevance_signals=["Series A", "funding round"],
            entity_focus=["OpenAI", "Anthropic"],
        )
        items = [
            ScrapedItem(
                url="https://example.com/article1",
                title="AI Startup Raises $50M",
                snippet="A promising AI startup announced...",
            ),
            ScrapedItem(
                url="https://example.com/article2",
                title="Tech Industry News",
                snippet="Various tech updates...",
            ),
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)

        mock_result_data = CuratedContent(
            items=[
                ScoredItem(
                    url="https://example.com/article1",
                    title="AI Startup Raises $50M",
                    relevance_score=85,
                    reasoning="Direct match for AI funding topic.",
                    key_excerpt="The startup raised $50M in Series A.",
                )
            ],
            summary="Found 1 highly relevant article about AI funding.",
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.curator.get_content_curator", return_value=mock_agent):
            result = await curate_content(input_data)

            mock_agent.run.assert_called_once()
            assert len(result.output.items) == 1
            assert result.output.items[0].relevance_score == 85
            assert result.output.summary == mock_result_data.summary

    @pytest.mark.asyncio
    async def test_curate_content_with_custom_model(self):
        """Test content curation with a custom model."""
        context = InterpretedContext(
            search_queries=["query"],
            relevance_signals=["signal"],
        )
        items = [ScrapedItem(url="https://example.com", title="Test", snippet="Test")]
        input_data = CuratorInput(interpreted_context=context, items=items)

        mock_result_data = CuratedContent(
            items=[],
            summary="No relevant content found.",
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        with patch("wintern.agents.curator.create_curator_agent") as mock_create:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_create.return_value = mock_agent

            result = await curate_content(input_data, model="openai/gpt-4")

            mock_create.assert_called_once_with("openai/gpt-4")
            assert result.output == mock_result_data

    @pytest.mark.asyncio
    async def test_curate_content_formats_input_correctly(self):
        """Test that input is formatted correctly before being sent to agent."""
        context = InterpretedContext(
            search_queries=["AI news"],
            relevance_signals=["artificial intelligence"],
            exclusion_criteria=["promotional"],
            entity_focus=["OpenAI"],
        )
        items = [
            ScrapedItem(
                url="https://example.com/article",
                title="AI Update",
                snippet="Latest AI developments...",
                source="example.com",
            )
        ]
        input_data = CuratorInput(interpreted_context=context, items=items)

        mock_result_data = CuratedContent(items=[], summary="No matches.")

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.curator.get_content_curator", return_value=mock_agent):
            await curate_content(input_data)

            call_args = mock_agent.run.call_args
            prompt = call_args[0][0]

            assert "## Interpreted Research Context" in prompt
            assert "- AI news" in prompt
            assert "- artificial intelligence" in prompt
            assert "- promotional" in prompt
            assert "- OpenAI" in prompt
            assert "### Item 1" in prompt
            assert "**Title**: AI Update" in prompt
            assert "**Source**: example.com" in prompt


# -----------------------------------------------------------------------------
# Integration-style Tests
# -----------------------------------------------------------------------------


class TestCuratorIntegration:
    """Integration-style tests for the curator module."""

    def test_full_input_output_cycle(self):
        """Test creating input, formatting, and validating output."""
        context = InterpretedContext(
            search_queries=[
                "AI startup funding 2024",
                "Series A AI companies",
                "machine learning VC investment",
            ],
            relevance_signals=[
                "funding round",
                "Series A",
                "Series B",
                "venture capital",
                "AI startup",
            ],
            exclusion_criteria=[
                "promotional content",
                "press release only",
                "unverified",
            ],
            entity_focus=["OpenAI", "Anthropic", "Mistral", "Cohere"],
        )

        items = [
            ScrapedItem(
                url="https://techcrunch.com/2024/01/15/ai-funding-news",
                title="AI Startup Raises $100M Series B",
                snippet="An AI startup focused on enterprise automation...",
                source="techcrunch.com",
                published_date="2024-01-15",
            ),
            ScrapedItem(
                url="https://example.com/pr/company-news",
                title="Company Announces New Features",
                snippet="Today we are excited to announce...",
                source="example.com",
            ),
            ScrapedItem(
                url="https://reuters.com/technology/ai-investment",
                title="VC Investment in AI Reaches Record High",
                snippet="Venture capital firms have invested record amounts...",
                source="reuters.com",
                published_date="2024-01-14",
            ),
        ]

        input_data = CuratorInput(interpreted_context=context, items=items)

        formatted = format_curator_input(input_data)

        assert "AI startup funding 2024" in formatted
        assert "funding round" in formatted
        assert "promotional content" in formatted
        assert "OpenAI" in formatted
        assert "techcrunch.com" in formatted
        assert "### Item 1" in formatted
        assert "### Item 2" in formatted
        assert "### Item 3" in formatted

        output = CuratedContent(
            items=[
                ScoredItem(
                    url="https://techcrunch.com/2024/01/15/ai-funding-news",
                    title="AI Startup Raises $100M Series B",
                    relevance_score=92,
                    reasoning="Direct match for AI funding, reputable source.",
                    key_excerpt="The startup raised $100M in Series B...",
                ),
                ScoredItem(
                    url="https://reuters.com/technology/ai-investment",
                    title="VC Investment in AI Reaches Record High",
                    relevance_score=88,
                    reasoning="Covers VC investment trends, authoritative.",
                    key_excerpt="VC investment in AI reached $50B...",
                ),
            ],
            summary="Found 2 highly relevant articles. One about specific "
            "funding and one about broader investment trends. The PR content "
            "was filtered out due to promotional nature.",
        )

        assert len(output.items) == 2
        assert output.items[0].relevance_score > output.items[1].relevance_score
        assert all(item.relevance_score >= 60 for item in output.items)
