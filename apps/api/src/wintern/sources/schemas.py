"""Schemas for data source results."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single search result from any data source.

    This is the common format that all data sources convert their results to,
    allowing uniform handling regardless of the source.
    """

    url: str = Field(..., description="The URL of the result")
    title: str = Field(..., description="The title of the result")
    snippet: str = Field(
        ...,
        description="A snippet or description of the content",
    )
    source: str = Field(
        ...,
        description="The data source identifier (e.g., 'brave_search', 'reddit')",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Publication date if available",
    )
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Additional source-specific metadata",
    )

    def to_scraped_item(self) -> ScrapedItemData:
        """Convert to ScrapedItem format for the curator agent.

        Returns:
            A dict compatible with ScrapedItem model.
        """
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "published_date": (self.published_at.isoformat() if self.published_at else None),
        }


# Type alias for the scraped item data dict
ScrapedItemData = dict[str, str | None]
