"""Brave Search API integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx

from wintern.core.config import settings
from wintern.sources.base import DataSource
from wintern.sources.schemas import SearchResult

logger = logging.getLogger(__name__)

# Brave Search API endpoint
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# Rate limiting state
_rate_limit_semaphore = asyncio.Semaphore(1)
_last_request_time: float = 0.0


def _get_min_request_interval() -> float:
    """Get the minimum interval between requests based on configured rate limit."""
    rps = settings.brave_rate_limit_rps
    if rps <= 0:
        return 0.0  # No rate limiting
    return 1.0 / rps


# Freshness filter options
FreshnessFilter = Literal["pd", "pw", "pm", "py"] | None


class BraveSearchError(Exception):
    """Base exception for Brave Search errors."""

    pass


class BraveAPIKeyMissingError(BraveSearchError):
    """Raised when Brave API key is not configured."""

    pass


class BraveRateLimitError(BraveSearchError):
    """Raised when rate limited by Brave API."""

    pass


class BraveAPIError(BraveSearchError):
    """Raised for general Brave API errors."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Brave API error ({status_code}): {message}")


def _parse_retry_after(value: str | None, default: int = 5) -> int:
    """Safely parse a Retry-After header value.

    The Retry-After header can be either:
    - An integer number of seconds (e.g., "120")
    - An HTTP-date (e.g., "Wed, 21 Oct 2015 07:28:00 GMT")

    Args:
        value: The Retry-After header value.
        default: Default seconds to return if parsing fails.

    Returns:
        Number of seconds to wait.
    """
    if not value:
        return default

    # Try parsing as integer first (most common)
    try:
        return int(value)
    except ValueError:
        pass

    # Try parsing as HTTP-date
    try:
        # HTTP-date format: "Wed, 21 Oct 2015 07:28:00 GMT"
        from email.utils import parsedate_to_datetime

        retry_dt = parsedate_to_datetime(value)
        now = datetime.now(UTC)
        delta = (retry_dt - now).total_seconds()
        return max(1, int(delta))  # At least 1 second
    except (ValueError, TypeError):
        pass

    return default


def _parse_age_to_datetime(age: str | None) -> datetime | None:
    """Parse Brave's age string into a UTC datetime.

    Brave returns age strings like "2 hours ago", "3 days ago", etc.

    Args:
        age: The age string from Brave API.

    Returns:
        A UTC-aware datetime object or None if parsing fails.
    """
    if not age:
        return None

    age = age.lower().strip()
    now = datetime.now(UTC)

    try:
        if "hour" in age:
            hours = int(age.split()[0])
            return now - timedelta(hours=hours)
        elif "day" in age:
            days = int(age.split()[0])
            return now - timedelta(days=days)
        elif "week" in age:
            weeks = int(age.split()[0])
            return now - timedelta(weeks=weeks)
        elif "month" in age:
            months = int(age.split()[0])
            return now - timedelta(days=months * 30)
        elif "year" in age:
            years = int(age.split()[0])
            return now - timedelta(days=years * 365)
    except (ValueError, IndexError):
        pass

    return None


async def _rate_limit() -> None:
    """Enforce rate limiting between requests."""
    global _last_request_time

    min_interval = _get_min_request_interval()
    if min_interval <= 0:
        return  # Rate limiting disabled

    async with _rate_limit_semaphore:
        loop = asyncio.get_running_loop()
        now = loop.time()
        time_since_last = now - _last_request_time

        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)

        _last_request_time = loop.time()


async def search_brave(
    query: str,
    *,
    count: int = 10,
    freshness: FreshnessFilter = None,
    max_retries: int = 3,
    timeout: float = 30.0,
) -> list[SearchResult]:
    """Search Brave Search API for web results.

    Args:
        query: The search query string.
        count: Maximum number of results to return (1-20).
        freshness: Filter by content age:
            - "pd": Past day (24 hours)
            - "pw": Past week
            - "pm": Past month
            - "py": Past year
            - None: No freshness filter
        max_retries: Maximum number of retry attempts for transient errors.
        timeout: Request timeout in seconds.

    Returns:
        A list of SearchResult objects.

    Raises:
        BraveAPIKeyMissingError: If BRAVE_API_KEY is not configured.
        BraveRateLimitError: If rate limited after retries.
        BraveAPIError: For other API errors.
    """
    if not settings.brave_api_key:
        raise BraveAPIKeyMissingError("BRAVE_API_KEY environment variable is not set")

    # Clamp count to valid range
    count = max(1, min(20, count))

    params: dict[str, str | int] = {
        "q": query,
        "count": count,
    }

    if freshness:
        params["freshness"] = freshness

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_api_key,
    }

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            await _rate_limit()

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    BRAVE_SEARCH_URL,
                    params=params,
                    headers=headers,
                )

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"), default=5)
                    logger.warning(
                        f"Brave API rate limited, waiting {retry_after}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_after)
                    last_error = BraveRateLimitError("Rate limited by Brave API")
                    continue

                if response.status_code >= 500:
                    # Server error - retry with backoff
                    wait_time = 2**attempt
                    logger.warning(
                        f"Brave API server error {response.status_code}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = BraveAPIError(response.status_code, "Server error")
                    continue

                response.raise_for_status()
                data = response.json()

                # Parse results
                results: list[SearchResult] = []
                web_results = data.get("web", {}).get("results", [])

                for item in web_results:
                    result = SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("description", ""),
                        source="brave_search",
                        published_at=_parse_age_to_datetime(item.get("age")),
                        metadata={
                            "language": item.get("language"),
                            "family_friendly": item.get("family_friendly"),
                        },
                    )
                    results.append(result)

                logger.debug(f"Brave search for '{query}' returned {len(results)} results")
                return results

        except httpx.HTTPStatusError as e:
            last_error = BraveAPIError(
                e.response.status_code,
                e.response.text[:200] if e.response.text else "Unknown error",
            )
            # Don't retry client errors (4xx except 429)
            if 400 <= e.response.status_code < 500:
                raise last_error from e

        except httpx.TimeoutException as e:
            wait_time = 2**attempt
            logger.warning(
                f"Brave API timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait_time)
            last_error = e

        except httpx.RequestError as e:
            wait_time = 2**attempt
            logger.warning(
                f"Brave API request error: {e}, retrying in {wait_time}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait_time)
            last_error = e

    # All retries exhausted
    if isinstance(last_error, BraveSearchError):
        raise last_error
    raise BraveAPIError(0, f"Request failed after {max_retries} attempts: {last_error}")


class BraveSearchSource(DataSource):
    """Brave Search data source implementation."""

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "brave_search"

    async def search(
        self,
        query: str,
        *,
        count: int = 10,
        **kwargs: object,
    ) -> list[SearchResult]:
        """Search Brave for the given query.

        Args:
            query: The search query string.
            count: Maximum number of results to return.
            **kwargs: Additional parameters:
                - freshness: FreshnessFilter for time-based filtering

        Returns:
            A list of SearchResult objects.
        """
        freshness = kwargs.get("freshness")
        if freshness is not None and freshness not in ("pd", "pw", "pm", "py"):
            freshness = None

        return await search_brave(
            query,
            count=count,
            freshness=freshness,  # type: ignore[arg-type]
        )

    async def health_check(self) -> bool:
        """Check if Brave Search is configured and available."""
        if not settings.brave_api_key:
            return False

        try:
            # Do a minimal search to verify API key works
            await search_brave("test", count=1)
            return True
        except BraveSearchError:
            return False


# Convenience instance
brave_search = BraveSearchSource()
