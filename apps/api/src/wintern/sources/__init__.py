"""Sources module - data source integrations (Brave, Reddit, etc.)."""

from wintern.sources.base import DataSource
from wintern.sources.brave import (
    BraveAPIError,
    BraveAPIKeyMissingError,
    BraveRateLimitError,
    BraveSearchError,
    BraveSearchSource,
    FreshnessFilter,
    brave_search,
    search_brave,
)
from wintern.sources.schemas import SearchResult

__all__ = [
    "BraveAPIError",
    "BraveAPIKeyMissingError",
    "BraveRateLimitError",
    "BraveSearchError",
    "BraveSearchSource",
    "DataSource",
    "FreshnessFilter",
    "SearchResult",
    "brave_search",
    "search_brave",
]
