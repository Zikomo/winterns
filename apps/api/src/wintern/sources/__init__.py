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
from wintern.sources.reddit import (
    RedditAPIError,
    RedditAuthError,
    RedditCredentialsMissingError,
    RedditError,
    RedditSource,
    TimeFilter,
    reddit_source,
    search_reddit,
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
    "RedditAPIError",
    "RedditAuthError",
    "RedditCredentialsMissingError",
    "RedditError",
    "RedditSource",
    "SearchResult",
    "TimeFilter",
    "brave_search",
    "reddit_source",
    "search_brave",
    "search_reddit",
]
