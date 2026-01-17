"""Content Curator Agent - Evaluates and scores scraped content for relevance.

This agent takes interpreted context (from the interpreter agent) along with
a list of scraped content items, and produces scored, filtered results
with relevance assessments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from wintern.agents.interpreter import InterpretedContext
from wintern.core.config import settings

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult


# -----------------------------------------------------------------------------
# Input Models
# -----------------------------------------------------------------------------


class ScrapedItem(BaseModel):
    """A single piece of scraped content to be evaluated.

    This represents content fetched from the web that needs to be
    evaluated for relevance to the user's research context.
    """

    url: str = Field(..., description="The URL where this content was found")
    title: str = Field(..., description="The title of the content")
    snippet: str = Field(
        ...,
        description="A snippet or summary of the content (may be truncated)",
    )
    source: str | None = Field(
        default=None,
        description="The source/domain of the content (e.g., 'techcrunch.com')",
    )
    published_date: str | None = Field(
        default=None,
        description="Publication date if available (ISO format preferred)",
    )


class CuratorInput(BaseModel):
    """Input to the content curator agent.

    Combines the interpreted context (from the interpreter agent) with
    a list of scraped items to be evaluated for relevance.
    """

    interpreted_context: InterpretedContext = Field(
        ...,
        description="The interpreted context from the interpreter agent",
    )
    items: list[ScrapedItem] = Field(
        ...,
        min_length=1,
        description="List of scraped items to evaluate",
    )


# -----------------------------------------------------------------------------
# Output Models
# -----------------------------------------------------------------------------


class ScoredItem(BaseModel):
    """A scraped item with relevance scoring and evaluation.

    Contains the original item information plus the curator's assessment
    of its relevance to the user's research needs.
    """

    url: str = Field(..., description="The URL of the evaluated content")
    title: str = Field(..., description="The title of the content")
    relevance_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Relevance score from 0-100",
    )
    reasoning: str = Field(
        ...,
        max_length=200,
        description="Brief explanation of the relevance score (1-2 sentences)",
    )
    key_excerpt: str | None = Field(
        default=None,
        description="A key excerpt if highly relevant (score 70+)",
    )


class CuratedContent(BaseModel):
    """Output from the content curator agent.

    Contains the evaluated and filtered items along with a summary
    of the overall findings.
    """

    items: list[ScoredItem] = Field(
        ...,
        description="Evaluated items with relevance scores (filtered to 60+)",
    )
    summary: str = Field(
        ...,
        description="Brief overview of the findings and content quality",
    )


# -----------------------------------------------------------------------------
# System Prompt
# -----------------------------------------------------------------------------

CURATOR_SYSTEM_PROMPT = """\
You are a content curator that evaluates web content for relevance to a user's \
research needs.

You will receive:
1. **Interpreted Context**: Contains search queries, relevance signals, exclusion \
criteria, and entity focus from the user's research goals
2. **Scraped Items**: A list of content items (URL, title, snippet) to evaluate

For each item, you must:
1. **Score relevance (0-100)** based on:
   - How well it matches the relevance signals
   - Whether it mentions entities of interest
   - Whether it avoids exclusion criteria
   - Content quality and credibility signals

2. **Provide brief reasoning** (1-2 sentences, max 200 chars) explaining the score

3. **Extract a key excerpt** if the item scores 70+ and contains a particularly \
valuable quote or insight

Scoring guidelines:
- 90-100: Exceptionally relevant, high-quality, authoritative source
- 70-89: Highly relevant, good quality, useful for research
- 60-69: Moderately relevant, may provide some value
- 40-59: Marginally relevant, limited usefulness
- 0-39: Not relevant or low quality, should be filtered out

**Important**: Only include items scoring 60 or above in your output. \
Filter out lower-scoring items entirely.

After evaluating all items, provide a brief summary (2-3 sentences) of:
- Overall quality of the content batch
- Key themes or patterns observed
- Any notable gaps or missing perspectives
"""


# -----------------------------------------------------------------------------
# Agent Definition
# -----------------------------------------------------------------------------


def create_curator_agent(model: str | None = None) -> Agent[None, CuratedContent]:
    """Create the content curator agent.

    Args:
        model: The model to use. Defaults to settings.default_model via OpenRouter.

    Returns:
        A configured Pydantic AI agent for content curation.
    """
    model_name = model or settings.default_model
    openrouter_model = f"openrouter:{model_name}"

    return Agent(
        openrouter_model,
        output_type=CuratedContent,
        system_prompt=CURATOR_SYSTEM_PROMPT,
    )


# Lazy-loaded default agent instance
_content_curator: Agent[None, CuratedContent] | None = None


def get_content_curator() -> Agent[None, CuratedContent]:
    """Get the default content curator agent (lazy initialization).

    This function lazily creates the agent on first access to avoid requiring
    API keys at import time, which is important for testing.

    Returns:
        The default content curator agent.
    """
    global _content_curator
    if _content_curator is None:
        _content_curator = create_curator_agent()
    return _content_curator


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def format_curator_input(input_data: CuratorInput) -> str:
    """Format the curator input as a prompt string for the agent.

    Args:
        input_data: The structured input containing context and items.

    Returns:
        A formatted string prompt for the agent.
    """
    ctx = input_data.interpreted_context

    # Format the interpreted context
    parts = ["## Interpreted Research Context"]

    parts.append("\n### Search Queries")
    parts.append("\n".join(f"- {q}" for q in ctx.search_queries))

    parts.append("\n### Relevance Signals")
    parts.append("\n".join(f"- {s}" for s in ctx.relevance_signals))

    if ctx.exclusion_criteria:
        parts.append("\n### Exclusion Criteria")
        parts.append("\n".join(f"- {e}" for e in ctx.exclusion_criteria))

    if ctx.entity_focus:
        parts.append("\n### Entities to Track")
        parts.append("\n".join(f"- {e}" for e in ctx.entity_focus))

    # Format the scraped items
    parts.append("\n## Content Items to Evaluate")

    for i, item in enumerate(input_data.items, 1):
        item_parts = [f"\n### Item {i}"]
        item_parts.append(f"**Title**: {item.title}")
        item_parts.append(f"**URL**: {item.url}")
        if item.source:
            item_parts.append(f"**Source**: {item.source}")
        if item.published_date:
            item_parts.append(f"**Published**: {item.published_date}")
        item_parts.append(f"**Snippet**: {item.snippet}")
        parts.append("\n".join(item_parts))

    return "\n".join(parts)


async def curate_content(
    input_data: CuratorInput,
    *,
    model: str | None = None,
) -> AgentRunResult[CuratedContent]:
    """Evaluate and score scraped content for relevance.

    This is the main entry point for the content curator. It takes the
    interpreted context and scraped items, then runs the agent to produce
    scored and filtered results.

    Args:
        input_data: The interpreted context and scraped items to evaluate.
        model: Optional model override. Defaults to settings.default_model.

    Returns:
        AgentRunResult containing the CuratedContent.

    Example:
        >>> context = InterpretedContext(
        ...     search_queries=["AI startup funding 2024"],
        ...     relevance_signals=["Series A", "funding round"],
        ... )
        >>> items = [ScrapedItem(url="...", title="...", snippet="...")]
        >>> input_data = CuratorInput(interpreted_context=context, items=items)
        >>> result = await curate_content(input_data)
        >>> print(result.output.items[0].relevance_score)
        85
    """
    agent = create_curator_agent(model) if model else get_content_curator()
    prompt = format_curator_input(input_data)
    return await agent.run(prompt)
