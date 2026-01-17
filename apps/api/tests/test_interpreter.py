"""Tests for the context interpreter agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from wintern.agents.interpreter import (
    ContextSourceType,
    InterpretedContext,
    InterpreterInput,
    SupplementaryContext,
    create_interpreter_agent,
    format_interpreter_input,
    interpret_context,
)

# -----------------------------------------------------------------------------
# Input Model Tests
# -----------------------------------------------------------------------------


class TestInterpreterInput:
    """Tests for the InterpreterInput model."""

    def test_minimal_input(self):
        """Test creating input with just context."""
        input_data = InterpreterInput(context="Track AI news")
        assert input_data.context == "Track AI news"
        assert input_data.objectives == []
        assert input_data.supplementary_content == []

    def test_full_input(self):
        """Test creating input with all fields."""
        input_data = InterpreterInput(
            context="Track AI developments at major tech companies",
            objectives=["Find recent announcements", "Monitor hiring trends"],
            supplementary_content=[
                SupplementaryContext(
                    source_type=ContextSourceType.TEXT,
                    content="Additional context here",
                    source_name="notes.txt",
                )
            ],
        )
        assert input_data.context == "Track AI developments at major tech companies"
        assert len(input_data.objectives) == 2
        assert len(input_data.supplementary_content) == 1

    def test_context_required(self):
        """Test that context field is required."""
        with pytest.raises(ValidationError, match="context"):
            InterpreterInput()  # type: ignore

    def test_context_cannot_be_empty(self):
        """Test that context cannot be empty string."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            InterpreterInput(context="")


class TestSupplementaryContext:
    """Tests for the SupplementaryContext model."""

    def test_minimal_supplementary_context(self):
        """Test creating supplementary context with just content."""
        supp = SupplementaryContext(content="Some extracted text")
        assert supp.content == "Some extracted text"
        assert supp.source_type == ContextSourceType.TEXT
        assert supp.source_name is None
        assert supp.mime_type is None
        assert supp.description is None

    def test_file_extract_context(self):
        """Test creating supplementary context from a file extract."""
        supp = SupplementaryContext(
            source_type=ContextSourceType.FILE_EXTRACT,
            content="Extracted PDF content...",
            source_name="report.pdf",
            mime_type="application/pdf",
            description="Q4 2024 market analysis report",
        )
        assert supp.source_type == ContextSourceType.FILE_EXTRACT
        assert supp.source_name == "report.pdf"
        assert supp.mime_type == "application/pdf"

    def test_url_content_context(self):
        """Test creating supplementary context from URL content."""
        supp = SupplementaryContext(
            source_type=ContextSourceType.URL_CONTENT,
            content="Content from the webpage...",
            source_name="https://example.com/article",
        )
        assert supp.source_type == ContextSourceType.URL_CONTENT


class TestContextSourceType:
    """Tests for the ContextSourceType enum."""

    def test_enum_values(self):
        """Test that expected enum values exist."""
        assert ContextSourceType.TEXT == "text"
        assert ContextSourceType.FILE_EXTRACT == "file_extract"
        assert ContextSourceType.URL_CONTENT == "url_content"


# -----------------------------------------------------------------------------
# Output Model Tests
# -----------------------------------------------------------------------------


class TestInterpretedContext:
    """Tests for the InterpretedContext output model."""

    def test_minimal_output(self):
        """Test creating output with required fields only."""
        output = InterpretedContext(
            search_queries=["AI news 2024"],
            relevance_signals=["artificial intelligence", "machine learning"],
        )
        assert len(output.search_queries) == 1
        assert len(output.relevance_signals) == 2
        assert output.exclusion_criteria == []
        assert output.entity_focus == []

    def test_full_output(self):
        """Test creating output with all fields."""
        output = InterpretedContext(
            search_queries=["AI news 2024", "machine learning trends"],
            relevance_signals=["artificial intelligence", "deep learning"],
            exclusion_criteria=["promotional content", "paywalled articles"],
            entity_focus=["OpenAI", "Google DeepMind", "Anthropic"],
        )
        assert len(output.search_queries) == 2
        assert len(output.exclusion_criteria) == 2
        assert len(output.entity_focus) == 3

    def test_search_queries_required(self):
        """Test that search_queries is required."""
        with pytest.raises(ValidationError, match="search_queries"):
            InterpretedContext(
                relevance_signals=["signal"],
            )  # type: ignore

    def test_search_queries_min_length(self):
        """Test that search_queries must have at least 1 item."""
        with pytest.raises(ValidationError, match="at least 1 item"):
            InterpretedContext(
                search_queries=[],
                relevance_signals=["signal"],
            )

    def test_search_queries_max_length(self):
        """Test that search_queries cannot exceed 10 items."""
        with pytest.raises(ValidationError, match="at most 10 items"):
            InterpretedContext(
                search_queries=[f"query {i}" for i in range(11)],
                relevance_signals=["signal"],
            )

    def test_relevance_signals_required(self):
        """Test that relevance_signals is required."""
        with pytest.raises(ValidationError, match="relevance_signals"):
            InterpretedContext(
                search_queries=["query"],
            )  # type: ignore

    def test_relevance_signals_min_length(self):
        """Test that relevance_signals must have at least 1 item."""
        with pytest.raises(ValidationError, match="at least 1 item"):
            InterpretedContext(
                search_queries=["query"],
                relevance_signals=[],
            )


# -----------------------------------------------------------------------------
# Format Input Tests
# -----------------------------------------------------------------------------


class TestFormatInterpreterInput:
    """Tests for the format_interpreter_input function."""

    def test_format_context_only(self):
        """Test formatting input with just context."""
        input_data = InterpreterInput(context="Track AI news")
        result = format_interpreter_input(input_data)
        assert "## Research Context" in result
        assert "Track AI news" in result
        assert "## Specific Objectives" not in result
        assert "## Supplementary Content" not in result

    def test_format_with_objectives(self):
        """Test formatting input with objectives."""
        input_data = InterpreterInput(
            context="Track AI news",
            objectives=["Find announcements", "Monitor trends"],
        )
        result = format_interpreter_input(input_data)
        assert "## Specific Objectives" in result
        assert "- Find announcements" in result
        assert "- Monitor trends" in result

    def test_format_with_supplementary_content(self):
        """Test formatting input with supplementary content."""
        input_data = InterpreterInput(
            context="Track AI news",
            supplementary_content=[
                SupplementaryContext(
                    content="Extra context from file",
                    source_name="notes.txt",
                    description="My research notes",
                )
            ],
        )
        result = format_interpreter_input(input_data)
        assert "## Supplementary Content" in result
        assert "### Supplementary Content 1 (notes.txt)" in result
        assert "*My research notes*" in result
        assert "Extra context from file" in result

    def test_format_multiple_supplementary(self):
        """Test formatting with multiple supplementary contexts."""
        input_data = InterpreterInput(
            context="Track AI news",
            supplementary_content=[
                SupplementaryContext(content="Content 1"),
                SupplementaryContext(content="Content 2", source_name="file.pdf"),
            ],
        )
        result = format_interpreter_input(input_data)
        assert "### Supplementary Content 1" in result
        assert "### Supplementary Content 2 (file.pdf)" in result


# -----------------------------------------------------------------------------
# Agent Tests (with mocking)
# -----------------------------------------------------------------------------


class TestCreateInterpreterAgent:
    """Tests for the create_interpreter_agent function."""

    def test_creates_agent_with_default_model(self):
        """Test that agent is created with default model from settings."""
        with (
            patch("wintern.agents.interpreter.settings") as mock_settings,
            patch("wintern.agents.interpreter.Agent") as mock_agent_class,
        ):
            mock_settings.default_model = "anthropic/claude-sonnet-4-20250514"
            mock_agent_class.return_value = MagicMock()

            agent = create_interpreter_agent()

            # Verify Agent was called with correct model format
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:anthropic/claude-sonnet-4-20250514"
            assert agent is not None

    def test_creates_agent_with_custom_model(self):
        """Test that agent can be created with a custom model."""
        with patch("wintern.agents.interpreter.Agent") as mock_agent_class:
            mock_agent_class.return_value = MagicMock()

            agent = create_interpreter_agent(model="openai/gpt-4")

            # Verify Agent was called with custom model
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[0][0] == "openrouter:openai/gpt-4"
            assert agent is not None


class TestInterpretContext:
    """Tests for the interpret_context function."""

    @pytest.mark.asyncio
    async def test_interpret_context_success(self):
        """Test successful context interpretation with mocked agent."""
        input_data = InterpreterInput(
            context="Track AI developments at major tech companies",
            objectives=["Find recent product announcements"],
        )

        # Create mock result
        mock_result_data = InterpretedContext(
            search_queries=[
                "AI product announcements 2024",
                "OpenAI new releases",
                "Google AI products launch",
            ],
            relevance_signals=[
                "product launch",
                "AI announcement",
                "new feature release",
            ],
            exclusion_criteria=["promotional content", "rumors"],
            entity_focus=["OpenAI", "Google", "Anthropic", "Meta AI"],
        )

        # Mock the agent's run method
        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.interpreter.get_context_interpreter", return_value=mock_agent):
            result = await interpret_context(input_data)

            # Verify the agent was called
            mock_agent.run.assert_called_once()

            # Verify the result
            assert result.output.search_queries == mock_result_data.search_queries
            assert result.output.relevance_signals == mock_result_data.relevance_signals
            assert result.output.exclusion_criteria == mock_result_data.exclusion_criteria
            assert result.output.entity_focus == mock_result_data.entity_focus

    @pytest.mark.asyncio
    async def test_interpret_context_with_custom_model(self):
        """Test context interpretation with a custom model."""
        input_data = InterpreterInput(context="Track AI news")

        mock_result_data = InterpretedContext(
            search_queries=["AI news"],
            relevance_signals=["artificial intelligence"],
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        with patch("wintern.agents.interpreter.create_interpreter_agent") as mock_create:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_create.return_value = mock_agent

            result = await interpret_context(input_data, model="openai/gpt-4")

            # Verify custom model was used
            mock_create.assert_called_once_with("openai/gpt-4")
            assert result.output == mock_result_data

    @pytest.mark.asyncio
    async def test_interpret_context_formats_input_correctly(self):
        """Test that input is formatted correctly before being sent to agent."""
        input_data = InterpreterInput(
            context="Track AI news",
            objectives=["Find announcements"],
            supplementary_content=[
                SupplementaryContext(content="Extra info", source_name="notes.txt")
            ],
        )

        mock_result_data = InterpretedContext(
            search_queries=["AI news"],
            relevance_signals=["AI"],
        )

        mock_agent_result = MagicMock()
        mock_agent_result.output = mock_result_data

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_result)

        with patch("wintern.agents.interpreter.get_context_interpreter", return_value=mock_agent):
            await interpret_context(input_data)

            # Get the prompt that was passed to the agent
            call_args = mock_agent.run.call_args
            prompt = call_args[0][0]

            # Verify the prompt contains expected sections
            assert "## Research Context" in prompt
            assert "Track AI news" in prompt
            assert "## Specific Objectives" in prompt
            assert "- Find announcements" in prompt
            assert "## Supplementary Content" in prompt
            assert "notes.txt" in prompt


# -----------------------------------------------------------------------------
# Integration-style Tests (still mocked, but testing full flow)
# -----------------------------------------------------------------------------


class TestInterpreterIntegration:
    """Integration-style tests for the interpreter module."""

    def test_full_input_output_cycle(self):
        """Test creating input, formatting, and validating output."""
        # Create complex input
        input_data = InterpreterInput(
            context="""I'm a venture capitalist focused on AI/ML startups.
            I need to stay updated on funding rounds, acquisitions, and new
            companies in the generative AI space.""",
            objectives=[
                "Track Series A and above funding rounds in AI",
                "Monitor acquisitions of AI startups by big tech",
                "Find emerging AI startups with novel approaches",
            ],
            supplementary_content=[
                SupplementaryContext(
                    source_type=ContextSourceType.FILE_EXTRACT,
                    content="Portfolio includes: Company A (NLP), Company B (Computer Vision)...",
                    source_name="portfolio.pdf",
                    mime_type="application/pdf",
                    description="Current portfolio companies",
                ),
                SupplementaryContext(
                    source_type=ContextSourceType.TEXT,
                    content="Focus areas: NLP, computer vision, robotics, autonomous systems",
                    description="Investment thesis notes",
                ),
            ],
        )

        # Format the input
        formatted = format_interpreter_input(input_data)

        # Verify formatting
        assert "venture capitalist" in formatted
        assert "Track Series A" in formatted
        assert "portfolio.pdf" in formatted
        assert "Investment thesis notes" in formatted

        # Create valid output
        output = InterpretedContext(
            search_queries=[
                "AI startup funding round 2024",
                "generative AI Series A funding",
                "big tech AI acquisition 2024",
                "emerging AI startups NLP",
                "computer vision startup funding",
            ],
            relevance_signals=[
                "funding round",
                "Series A",
                "Series B",
                "acquisition",
                "generative AI",
                "LLM",
                "startup",
            ],
            exclusion_criteria=[
                "press releases only",
                "rumor",
                "unconfirmed",
                "pre-seed",  # Too early stage
            ],
            entity_focus=[
                "OpenAI",
                "Anthropic",
                "Mistral",
                "Cohere",
                "Stability AI",
            ],
        )

        # Verify output is valid
        assert len(output.search_queries) == 5
        assert len(output.relevance_signals) == 7
        assert len(output.exclusion_criteria) == 4
        assert len(output.entity_focus) == 5
