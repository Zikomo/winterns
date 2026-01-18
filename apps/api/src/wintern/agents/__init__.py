"""Agents module - Pydantic AI agents (interpreter, curator, composer)."""

from wintern.agents.composer import (
    ComposerInput,
    DeliveryChannel,
    DigestContent,
    UserContext,
    compose_digest,
    create_composer_agent,
    format_composer_input,
    get_digest_composer,
)
from wintern.agents.curator import (
    CuratedContent,
    CuratorInput,
    ScoredItem,
    ScrapedItem,
    create_curator_agent,
    curate_content,
    format_curator_input,
    get_content_curator,
)
from wintern.agents.interpreter import (
    ContextSourceType,
    InterpretedContext,
    InterpreterInput,
    SupplementaryContext,
    create_interpreter_agent,
    format_interpreter_input,
    get_context_interpreter,
    interpret_context,
)

__all__ = [
    "ComposerInput",
    "ContextSourceType",
    "CuratedContent",
    "CuratorInput",
    "DeliveryChannel",
    "DigestContent",
    "InterpretedContext",
    "InterpreterInput",
    "ScoredItem",
    "ScrapedItem",
    "SupplementaryContext",
    "UserContext",
    "compose_digest",
    "create_composer_agent",
    "create_curator_agent",
    "create_interpreter_agent",
    "curate_content",
    "format_composer_input",
    "format_curator_input",
    "format_interpreter_input",
    "get_content_curator",
    "get_context_interpreter",
    "get_digest_composer",
    "interpret_context",
]
