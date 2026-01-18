"""Digest Composer Agent - Formats curated content into deliverable digests.

This agent takes curated content (from the curator agent) along with delivery
channel preferences and user context, and produces formatted digests ready
for delivery via email, Slack, or SMS.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from wintern.agents.curator import CuratedContent
from wintern.core.config import settings

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult


# -----------------------------------------------------------------------------
# Input Models
# -----------------------------------------------------------------------------


class DeliveryChannel(str, enum.Enum):
    """Supported delivery channels for digests."""

    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"


class UserContext(BaseModel):
    """Context about the user receiving the digest.

    This helps personalize the digest content and tone.
    """

    name: str | None = Field(
        default=None,
        description="User's name for personalization",
    )
    preferences: str | None = Field(
        default=None,
        description="Any user preferences or notes about their interests",
    )
    timezone: str | None = Field(
        default=None,
        description="User's timezone for date/time formatting",
    )


class ComposerInput(BaseModel):
    """Input to the digest composer agent.

    Combines the curated content with delivery channel and user context
    to produce a properly formatted digest.
    """

    curated_content: CuratedContent = Field(
        ...,
        description="The curated content from the curator agent",
    )
    channel: DeliveryChannel = Field(
        ...,
        description="The delivery channel to format for",
    )
    user_context: UserContext = Field(
        default_factory=UserContext,
        description="Context about the user for personalization",
    )
    research_topic: str | None = Field(
        default=None,
        description="The original research topic for context in the digest",
    )


# -----------------------------------------------------------------------------
# Output Models
# -----------------------------------------------------------------------------


class DigestContent(BaseModel):
    """Output from the digest composer agent.

    Contains the formatted digest in multiple formats, allowing the delivery
    system to choose the appropriate format for the channel.
    """

    subject: str = Field(
        ...,
        max_length=100,
        description="Message subject/title (max 100 chars)",
    )
    body_html: str = Field(
        ...,
        description="HTML formatted body for email delivery",
    )
    body_plain: str = Field(
        ...,
        description="Plain text fallback for email or basic display",
    )
    body_slack: str = Field(
        ...,
        description="Slack mrkdwn formatted body",
    )
    item_count: int = Field(
        ...,
        ge=0,
        description="Number of items included in the digest",
    )


# -----------------------------------------------------------------------------
# System Prompt
# -----------------------------------------------------------------------------

COMPOSER_SYSTEM_PROMPT = """\
You are a digest composer that formats curated research content for delivery.

You will receive:
1. **Curated Content**: A list of scored items with relevance scores, reasoning, \
and key excerpts, plus a summary
2. **Delivery Channel**: The target channel (email, slack, or sms)
3. **User Context**: Optional user info for personalization
4. **Research Topic**: The topic being researched

Your job is to create an engaging, scannable digest that:
- Has a compelling subject line (max 100 characters)
- Highlights why each item matters to the user
- Prioritizes the most relevant items first (by relevance score)
- Provides appropriate formats for each channel

## Format Guidelines

### HTML (body_html)
- Use clean, semantic HTML
- Include inline styles for email compatibility
- Structure with headings, paragraphs, and lists
- Make links clickable with proper href attributes
- Keep it readable and scannable

### Plain Text (body_plain)
- No formatting markers, just clean text
- Use line breaks and spacing for structure
- Include full URLs (not hidden behind link text)
- Keep it simple and readable

### Slack mrkdwn (body_slack)
- Use Slack-compatible mrkdwn syntax:
  - *bold* for emphasis
  - _italic_ for titles or subtle emphasis
  - <url|display text> for links
  - Use bullet points with •
  - Use >>> for blockquotes if needed
- Keep it concise and scannable

## Channel-Specific Behavior

- **Email**: Full detail, rich HTML formatting, comprehensive coverage
- **Slack**: Moderate detail, focus on quick scanning, link-heavy
- **SMS**: Ultra-condensed, only the most critical 1-2 items, plain text only

For SMS, the body_html and body_slack should still be generated but the body_plain \
should be extremely brief (under 160 characters ideally).

## Quality Guidelines

- Start with a brief greeting if user name is available
- Lead with the most important/relevant finding
- For each item, explain WHY it's relevant (use the reasoning)
- Include key excerpts when available
- End with a brief sign-off
- Match the tone to the channel (professional for email, casual for Slack)
"""


# -----------------------------------------------------------------------------
# Agent Definition
# -----------------------------------------------------------------------------


def create_composer_agent(model: str | None = None) -> Agent[None, DigestContent]:
    """Create the digest composer agent.

    Args:
        model: The model to use. Defaults to settings.default_model via OpenRouter.

    Returns:
        A configured Pydantic AI agent for digest composition.
    """
    model_name = model or settings.default_model
    openrouter_model = f"openrouter:{model_name}"

    return Agent(
        openrouter_model,
        output_type=DigestContent,
        system_prompt=COMPOSER_SYSTEM_PROMPT,
    )


# Lazy-loaded default agent instance
_digest_composer: Agent[None, DigestContent] | None = None


def get_digest_composer() -> Agent[None, DigestContent]:
    """Get the default digest composer agent (lazy initialization).

    This function lazily creates the agent on first access to avoid requiring
    API keys at import time, which is important for testing.

    Returns:
        The default digest composer agent.
    """
    global _digest_composer
    if _digest_composer is None:
        _digest_composer = create_composer_agent()
    return _digest_composer


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def format_composer_input(input_data: ComposerInput) -> str:
    """Format the composer input as a prompt string for the agent.

    Args:
        input_data: The structured input containing curated content and preferences.

    Returns:
        A formatted string prompt for the agent.
    """
    parts = []

    # Research topic
    if input_data.research_topic:
        parts.append(f"## Research Topic\n{input_data.research_topic}")

    # Delivery channel
    parts.append(f"\n## Delivery Channel\n{input_data.channel.value.upper()}")

    # User context
    user_ctx = input_data.user_context
    if user_ctx.name or user_ctx.preferences or user_ctx.timezone:
        ctx_parts = ["## User Context"]
        if user_ctx.name:
            ctx_parts.append(f"- **Name**: {user_ctx.name}")
        if user_ctx.preferences:
            ctx_parts.append(f"- **Preferences**: {user_ctx.preferences}")
        if user_ctx.timezone:
            ctx_parts.append(f"- **Timezone**: {user_ctx.timezone}")
        parts.append("\n".join(ctx_parts))

    # Curated content summary
    curated = input_data.curated_content
    parts.append(f"\n## Content Summary\n{curated.summary}")

    # Curated items
    parts.append(f"\n## Curated Items ({len(curated.items)} total)")

    for i, item in enumerate(curated.items, 1):
        item_parts = [f"\n### Item {i} (Score: {item.relevance_score}/100)"]
        item_parts.append(f"**Title**: {item.title}")
        item_parts.append(f"**URL**: {item.url}")
        item_parts.append(f"**Why relevant**: {item.reasoning}")
        if item.key_excerpt:
            item_parts.append(f'**Key excerpt**: "{item.key_excerpt}"')
        parts.append("\n".join(item_parts))

    return "\n".join(parts)


async def compose_digest(
    input_data: ComposerInput,
    *,
    model: str | None = None,
) -> AgentRunResult[DigestContent]:
    """Compose a digest from curated content.

    This is the main entry point for the digest composer. It takes the
    curated content and delivery preferences, then runs the agent to produce
    a formatted digest.

    Args:
        input_data: The curated content and delivery preferences.
        model: Optional model override. Defaults to settings.default_model.

    Returns:
        AgentRunResult containing the DigestContent.

    Example:
        >>> curated = CuratedContent(items=[...], summary="...")
        >>> input_data = ComposerInput(
        ...     curated_content=curated,
        ...     channel=DeliveryChannel.EMAIL,
        ...     user_context=UserContext(name="Alice"),
        ... )
        >>> result = await compose_digest(input_data)
        >>> print(result.output.subject)
        "Your AI Research Digest: 3 Key Findings"
    """
    agent = create_composer_agent(model) if model else get_digest_composer()
    prompt = format_composer_input(input_data)
    return await agent.run(prompt)
