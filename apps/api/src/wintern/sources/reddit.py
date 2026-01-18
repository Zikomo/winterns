"""Reddit data source using AsyncPRAW."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

import asyncpraw
import asyncpraw.reddit
from asyncprawcore.exceptions import (
    AsyncPrawcoreException,
    Forbidden,
    NotFound,
    ResponseException,
)

from wintern.core.config import settings
from wintern.sources.base import DataSource
from wintern.sources.schemas import SearchResult

logger = logging.getLogger(__name__)

# Time filter options matching Reddit's API
TimeFilter = Literal["hour", "day", "week", "month", "year", "all"]


class RedditError(Exception):
    """Base exception for Reddit errors."""

    pass


class RedditCredentialsMissingError(RedditError):
    """Raised when Reddit credentials are not configured."""

    pass


class RedditAuthError(RedditError):
    """Raised when authentication fails."""

    pass


class RedditAPIError(RedditError):
    """Raised for general Reddit API errors."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Reddit API error: {message}")


def _create_reddit_client() -> asyncpraw.Reddit:
    """Create an AsyncPRAW Reddit client instance.

    Returns:
        Configured AsyncPRAW Reddit client.

    Raises:
        RedditCredentialsMissingError: If credentials are not configured.
    """
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        raise RedditCredentialsMissingError(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables must be set"
        )

    return asyncpraw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )


def _submission_to_search_result(submission: asyncpraw.reddit.Submission) -> SearchResult:
    """Convert an AsyncPRAW Submission to a SearchResult.

    Args:
        submission: AsyncPRAW Submission object.

    Returns:
        SearchResult representation of the submission.
    """
    # Build snippet from selftext or title
    selftext = getattr(submission, "selftext", "") or ""
    snippet = selftext[:500] if selftext else submission.title

    # Parse created_utc to datetime
    published_at = None
    if hasattr(submission, "created_utc") and submission.created_utc:
        try:
            published_at = datetime.fromtimestamp(submission.created_utc, tz=UTC)
        except (ValueError, OSError, OverflowError):
            pass

    return SearchResult(
        url=f"https://www.reddit.com{submission.permalink}",
        title=submission.title,
        snippet=snippet,
        source="reddit",
        published_at=published_at,
        metadata={
            "subreddit": str(submission.subreddit),
            "author": str(submission.author) if submission.author else "[deleted]",
            "score": submission.score,
            "num_comments": submission.num_comments,
            "is_self": submission.is_self,
            "domain": getattr(submission, "domain", None),
        },
    )


async def search_reddit(
    query: str,
    *,
    subreddits: list[str] | None = None,
    time_filter: TimeFilter = "week",
    count: int = 25,
) -> list[SearchResult]:
    """Search Reddit for posts matching the query.

    Args:
        query: The search query string.
        subreddits: List of subreddits to search in (None for all Reddit).
        time_filter: Time filter for results:
            - "hour": Past hour
            - "day": Past 24 hours
            - "week": Past week
            - "month": Past month
            - "year": Past year
            - "all": All time
        count: Maximum number of results to return (1-100).

    Returns:
        A list of SearchResult objects.

    Raises:
        RedditCredentialsMissingError: If Reddit credentials are not configured.
        RedditAuthError: If authentication fails.
        RedditAPIError: For other API errors.
    """
    # Clamp count to valid range
    count = max(1, min(100, count))

    reddit = _create_reddit_client()

    try:
        results: list[SearchResult] = []

        if subreddits:
            # Search within specific subreddits
            subreddit_str = "+".join(subreddits)
            subreddit = await reddit.subreddit(subreddit_str)
        else:
            # Search all of Reddit
            subreddit = await reddit.subreddit("all")

        async for submission in subreddit.search(
            query,
            sort="relevance",
            time_filter=time_filter,
            limit=count,
        ):
            # Skip removed/deleted posts
            if getattr(submission, "removed_by_category", None):
                continue

            results.append(_submission_to_search_result(submission))

        logger.debug(f"Reddit search for '{query}' returned {len(results)} results")
        return results

    except Forbidden as e:
        raise RedditAuthError(f"Access forbidden: {e}") from e
    except NotFound as e:
        raise RedditAPIError(f"Resource not found: {e}") from e
    except ResponseException as e:
        raise RedditAPIError(f"Response error: {e}") from e
    except AsyncPrawcoreException as e:
        raise RedditAPIError(str(e)) from e
    finally:
        await reddit.close()


class RedditSource(DataSource):
    """Reddit data source implementation using AsyncPRAW."""

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "reddit"

    async def search(
        self,
        query: str,
        *,
        count: int = 25,
        **kwargs: object,
    ) -> list[SearchResult]:
        """Search Reddit for the given query.

        Args:
            query: The search query string.
            count: Maximum number of results to return.
            **kwargs: Additional parameters:
                - subreddits: list[str] for specific subreddit search
                - time_filter: TimeFilter for time-based filtering

        Returns:
            A list of SearchResult objects.
        """
        subreddits = kwargs.get("subreddits")
        if subreddits is not None and not isinstance(subreddits, list):
            subreddits = None

        time_filter = kwargs.get("time_filter", "week")
        if time_filter not in ("hour", "day", "week", "month", "year", "all"):
            time_filter = "week"

        return await search_reddit(
            query,
            subreddits=subreddits,
            time_filter=time_filter,  # type: ignore[arg-type]
            count=count,
        )

    async def health_check(self) -> bool:
        """Check if Reddit is configured and available."""
        if not settings.reddit_client_id or not settings.reddit_client_secret:
            return False

        try:
            reddit = _create_reddit_client()
            try:
                # Verify credentials by making an authenticated API call
                # user.me() returns None for app-only auth but validates the credentials
                await reddit.user.me()
                return True
            finally:
                await reddit.close()
        except (RedditError, AsyncPrawcoreException):
            return False


# Convenience instance
reddit_source = RedditSource()
