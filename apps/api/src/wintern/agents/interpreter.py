"""Context Interpreter Agent - Analyzes user context and generates search queries.

This agent takes a user's freeform context description and objectives,
and produces structured output for web research: search queries, relevance
signals, exclusion criteria, and entities to track.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from wintern.core.config import settings

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult


# -----------------------------------------------------------------------------
# Input Models
# -----------------------------------------------------------------------------


class ContextSourceType(str, enum.Enum):
    """Type of context source - extensible for future file support."""

    TEXT = "text"  # User-provided text context
    FILE_EXTRACT = "file_extract"  # Text extracted from a file (PDF, doc, etc.)
    URL_CONTENT = "url_content"  # Content fetched from a URL


class SupplementaryContext(BaseModel):
    """Additional context from files or other sources.

    This model is designed to be extended for file-based context in the future.
    When files are uploaded, they'll be processed and the extracted content
    passed here with appropriate metadata.
    """

    source_type: ContextSourceType = ContextSourceType.TEXT
    content: str = Field(..., description="The extracted or provided content")
    source_name: str | None = Field(
        default=None,
        description="Name of the source (e.g., filename, URL)",
    )
    mime_type: str | None = Field(
        default=None,
        description="MIME type if from a file (e.g., application/pdf)",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of what this context contains",
    )


class InterpreterInput(BaseModel):
    """Input to the context interpreter agent.

    Designed to support both current text-only context and future file-based
    context. The main context field holds the user's freeform description,
    while supplementary_content can hold additional context from files,
    URLs, or other sources.
    """

    context: str = Field(
        ...,
        min_length=1,
        description="The user's primary context - what they want to research",
    )
    objectives: list[str] = Field(
        default_factory=list,
        description="Specific objectives or questions to answer",
    )
    supplementary_content: list[SupplementaryContext] = Field(
        default_factory=list,
        description="Additional context from files, URLs, or other sources",
    )


# -----------------------------------------------------------------------------
# Output Models
# -----------------------------------------------------------------------------


class InterpretedContext(BaseModel):
    """Output from the context interpreter agent.

    Contains structured information for conducting web research based on
    the user's context and objectives.
    """

    search_queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Concrete search queries to execute against search engines",
    )
    relevance_signals: list[str] = Field(
        ...,
        min_length=1,
        description="Signals that indicate content is relevant to the user's needs",
    )
    exclusion_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria for filtering out irrelevant or unwanted content",
    )
    entity_focus: list[str] = Field(
        default_factory=list,
        description="Specific entities (companies, people, products, topics) to track",
    )


# -----------------------------------------------------------------------------
# System Prompt
# -----------------------------------------------------------------------------

INTERPRETER_SYSTEM_PROMPT = """\
You are a research context interpreter. Your job is to analyze a user's research \
context and objectives, then produce structured output to guide web research.

Given the user's context (their freeform description of what they want to research) \
and any specific objectives they have, determine:

1. **Search Queries** (1-10): Concrete search queries that will find relevant content. \
These will be used directly with search engines like Brave Search. Make them specific \
and varied to cover different aspects of the research topic. Include both broad \
overview queries and specific detail queries.

2. **Relevance Signals**: Key phrases, terms, concepts, or characteristics that \
indicate content is relevant to the user's needs. These help filter and rank results.

3. **Exclusion Criteria**: Types of content, sources, or topics to filter out. \
For example: "promotional content", "outdated information (pre-2023)", \
"unverified claims", "paywall-only sources".

4. **Entity Focus**: Specific entities the user wants to track - companies, people, \
products, technologies, or topics. These help prioritize content mentioning these entities.

Guidelines:
- Search queries should be web-search optimized (not questions, but keyword phrases)
- Consider recency - add date qualifiers when freshness matters
- Think about different angles: news, technical, business, academic perspectives
- Be specific enough to avoid noise but broad enough to find diverse sources
- If the user provides supplementary content (from files, etc.), use it to inform \
  your understanding but focus on generating queries for web research
"""


# -----------------------------------------------------------------------------
# Agent Definition
# -----------------------------------------------------------------------------


def create_interpreter_agent(model: str | None = None) -> Agent[None, InterpretedContext]:
    """Create the context interpreter agent.

    Args:
        model: The model to use. Defaults to settings.default_model via OpenRouter.

    Returns:
        A configured Pydantic AI agent for context interpretation.
    """
    model_name = model or settings.default_model
    # OpenRouter format: "openrouter:<provider>/<model>"
    openrouter_model = f"openrouter:{model_name}"

    return Agent(
        openrouter_model,
        output_type=InterpretedContext,
        system_prompt=INTERPRETER_SYSTEM_PROMPT,
    )


# Lazy-loaded default agent instance
_context_interpreter: Agent[None, InterpretedContext] | None = None


def get_context_interpreter() -> Agent[None, InterpretedContext]:
    """Get the default context interpreter agent (lazy initialization).

    This function lazily creates the agent on first access to avoid requiring
    API keys at import time, which is important for testing.

    Returns:
        The default context interpreter agent.
    """
    global _context_interpreter
    if _context_interpreter is None:
        _context_interpreter = create_interpreter_agent()
    return _context_interpreter


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def format_interpreter_input(input_data: InterpreterInput) -> str:
    """Format the interpreter input as a prompt string for the agent.

    Args:
        input_data: The structured input containing context and objectives.

    Returns:
        A formatted string prompt for the agent.
    """
    parts = [f"## Research Context\n{input_data.context}"]

    if input_data.objectives:
        objectives_text = "\n".join(f"- {obj}" for obj in input_data.objectives)
        parts.append(f"\n## Specific Objectives\n{objectives_text}")

    if input_data.supplementary_content:
        supplementary_parts = []
        for i, supp in enumerate(input_data.supplementary_content, 1):
            header = f"### Supplementary Content {i}"
            if supp.source_name:
                header += f" ({supp.source_name})"
            if supp.description:
                header += f"\n*{supp.description}*"
            supplementary_parts.append(f"{header}\n{supp.content}")

        parts.append("\n## Supplementary Content\n" + "\n\n".join(supplementary_parts))

    return "\n".join(parts)


async def interpret_context(
    input_data: InterpreterInput,
    *,
    model: str | None = None,
) -> AgentRunResult[InterpretedContext]:
    """Interpret user context and generate search parameters.

    This is the main entry point for the context interpreter. It takes structured
    input, formats it appropriately, and runs the agent to produce interpreted
    context for web research.

    Args:
        input_data: The user's context and objectives.
        model: Optional model override. Defaults to settings.default_model.

    Returns:
        AgentRunResult containing the InterpretedContext.

    Example:
        >>> input_data = InterpreterInput(
        ...     context="I want to track AI developments at major tech companies",
        ...     objectives=["Find recent AI product announcements", "Track hiring trends"]
        ... )
        >>> result = await interpret_context(input_data)
        >>> print(result.data.search_queries)
        ['AI announcements Google 2024', 'OpenAI product launches', ...]
    """
    agent = create_interpreter_agent(model) if model else get_context_interpreter()
    prompt = format_interpreter_input(input_data)
    return await agent.run(prompt)
