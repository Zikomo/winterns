"""Schemas for delivery channels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class DeliveryItem(BaseModel):
    """A content item to include in the delivery.

    This is a simplified view of ScoredItem for delivery purposes.
    """

    url: str = Field(..., description="The URL of the content")
    title: str = Field(..., description="The title of the content")
    relevance_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Relevance score from 0-100",
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of the relevance score",
    )
    key_excerpt: str | None = Field(
        default=None,
        description="A key excerpt if available",
    )


class DeliveryPayload(BaseModel):
    """Payload for delivering a digest.

    Contains the formatted content ready for delivery to any channel.
    """

    subject: str = Field(
        ...,
        description="The subject/header of the digest",
    )
    body: str = Field(
        ...,
        description="The body text of the digest (may include markdown)",
    )
    items: list[DeliveryItem] = Field(
        default_factory=list,
        description="Content items to include in the digest",
    )


class DeliveryResult(BaseModel):
    """Result of a delivery attempt."""

    success: bool = Field(
        ...,
        description="Whether the delivery succeeded",
    )
    channel: str = Field(
        ...,
        description="The delivery channel used",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if delivery failed",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the delivery was attempted",
    )
