"""Reddit API integration."""

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

# Reddit API endpoints
REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_SEARCH_URL = "https://oauth.reddit.com/search"
REDDIT_SUBREDDIT_SEARCH_URL = "https://oauth.reddit.com/r/{subreddit}/search"

# Rate limiting state (Reddit allows 60 requests/minute)
_rate_limit_semaphore = asyncio.Semaphore(1)
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 1.0  # 1 request per second = 60/minute


# Time filter options
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


class RedditRateLimitError(RedditError):
    """Raised when rate limited by Reddit API."""

    pass


class RedditAPIError(RedditError):
    """Raised for general Reddit API errors."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Reddit API error ({status_code}): {message}")


def _parse_created_utc(timestamp: float | None) -> datetime | None:
    """Parse Reddit's created_utc timestamp into a UTC datetime.

    Args:
        timestamp: Unix timestamp from Reddit API.

    Returns:
        A UTC-aware datetime object or None if parsing fails.
    """
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


async def _rate_limit() -> None:
    """Enforce rate limiting between requests."""
    global _last_request_time

    async with _rate_limit_semaphore:
        loop = asyncio.get_running_loop()
        now = loop.time()
        time_since_last = now - _last_request_time

        if time_since_last < _MIN_REQUEST_INTERVAL:
            await asyncio.sleep(_MIN_REQUEST_INTERVAL - time_since_last)

        _last_request_time = loop.time()


class RedditClient:
    """Reddit API client with OAuth2 authentication."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
    ) -> None:
        """Initialize the Reddit client.

        Args:
            client_id: Reddit OAuth client ID.
            client_secret: Reddit OAuth client secret.
            user_agent: User agent string for API requests.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._token: str | None = None
        self._token_expires: datetime | None = None

    async def _get_token(self, timeout: float = 30.0) -> str:
        """Get a valid access token, refreshing if necessary.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            A valid access token.

        Raises:
            RedditAuthError: If authentication fails.
        """
        now = datetime.now(UTC)

        # Return cached token if still valid
        if self._token and self._token_expires and now < self._token_expires:
            return self._token

        # Request new token
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    REDDIT_AUTH_URL,
                    auth=(self.client_id, self.client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"User-Agent": self.user_agent},
                )

                if response.status_code == 401:
                    raise RedditAuthError("Invalid Reddit credentials")

                response.raise_for_status()
                data = response.json()

                token: str = data["access_token"]
                self._token = token
                # Refresh 60 seconds before expiry
                expires_in = data.get("expires_in", 3600)
                self._token_expires = now + timedelta(seconds=expires_in - 60)

                logger.debug("Reddit OAuth token refreshed")
                return token

        except httpx.HTTPStatusError as e:
            raise RedditAuthError(f"Authentication failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise RedditAuthError(f"Authentication request failed: {e}") from e

    def clear_token(self) -> None:
        """Clear the cached token, forcing re-authentication."""
        self._token = None
        self._token_expires = None


async def search_reddit(
    query: str,
    *,
    subreddits: list[str] | None = None,
    time_filter: TimeFilter = "week",
    count: int = 25,
    max_retries: int = 3,
    timeout: float = 30.0,
    client: RedditClient | None = None,
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
        max_retries: Maximum number of retry attempts for transient errors.
        timeout: Request timeout in seconds.
        client: Optional pre-configured RedditClient instance.

    Returns:
        A list of SearchResult objects.

    Raises:
        RedditCredentialsMissingError: If Reddit credentials are not configured.
        RedditAuthError: If authentication fails.
        RedditRateLimitError: If rate limited after retries.
        RedditAPIError: For other API errors.
    """
    # Check credentials
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        raise RedditCredentialsMissingError(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables must be set"
        )

    # Use provided client or create one
    if client is None:
        client = RedditClient(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

    # Clamp count to valid range
    count = max(1, min(100, count))

    # Build search URL
    if subreddits:
        # Search within specific subreddits
        subreddit_str = "+".join(subreddits)
        url = REDDIT_SUBREDDIT_SEARCH_URL.format(subreddit=subreddit_str)
    else:
        url = REDDIT_SEARCH_URL

    params: dict[str, str | int] = {
        "q": query,
        "limit": count,
        "t": time_filter,
        "sort": "relevance",
        "type": "link",  # Only search posts, not comments
    }

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            await _rate_limit()

            token = await client._get_token(timeout=timeout)
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": client.user_agent,
            }

            async with httpx.AsyncClient(timeout=timeout) as http_client:
                response = await http_client.get(
                    url,
                    params=params,
                    headers=headers,
                )

                if response.status_code == 401:
                    # Token might have expired, clear and retry
                    client.clear_token()
                    last_error = RedditAuthError("Token expired")
                    continue

                if response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning(
                        f"Reddit API rate limited, waiting {retry_after}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_after)
                    last_error = RedditRateLimitError("Rate limited by Reddit API")
                    continue

                if response.status_code >= 500:
                    # Server error - retry with backoff
                    wait_time = 2**attempt
                    logger.warning(
                        f"Reddit API server error {response.status_code}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = RedditAPIError(response.status_code, "Server error")
                    continue

                response.raise_for_status()
                data = response.json()

                # Parse results
                results: list[SearchResult] = []
                posts = data.get("data", {}).get("children", [])

                for post in posts:
                    post_data = post.get("data", {})

                    # Skip removed/deleted posts
                    if post_data.get("removed_by_category") or post_data.get("removed"):
                        continue

                    # Build snippet from selftext or title
                    selftext = post_data.get("selftext", "")
                    snippet = selftext[:500] if selftext else post_data.get("title", "")

                    result = SearchResult(
                        url=f"https://www.reddit.com{post_data.get('permalink', '')}",
                        title=post_data.get("title", ""),
                        snippet=snippet,
                        source="reddit",
                        published_at=_parse_created_utc(post_data.get("created_utc")),
                        metadata={
                            "subreddit": post_data.get("subreddit"),
                            "author": post_data.get("author"),
                            "score": post_data.get("score"),
                            "num_comments": post_data.get("num_comments"),
                            "is_self": post_data.get("is_self"),
                            "domain": post_data.get("domain"),
                        },
                    )
                    results.append(result)

                logger.debug(f"Reddit search for '{query}' returned {len(results)} results")
                return results

        except httpx.HTTPStatusError as e:
            last_error = RedditAPIError(
                e.response.status_code,
                e.response.text[:200] if e.response.text else "Unknown error",
            )
            # Don't retry client errors (4xx except 429 and 401)
            if 400 <= e.response.status_code < 500 and e.response.status_code not in (
                401,
                429,
            ):
                raise last_error from e

        except httpx.TimeoutException as e:
            wait_time = 2**attempt
            logger.warning(
                f"Reddit API timeout, retrying in {wait_time}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait_time)
            last_error = e

        except httpx.RequestError as e:
            wait_time = 2**attempt
            logger.warning(
                f"Reddit API request error: {e}, retrying in {wait_time}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait_time)
            last_error = e

    # All retries exhausted
    if isinstance(last_error, RedditError):
        raise last_error
    raise RedditAPIError(0, f"Request failed after {max_retries} attempts: {last_error}")


class RedditSource(DataSource):
    """Reddit data source implementation."""

    def __init__(self) -> None:
        """Initialize the Reddit source."""
        self._client: RedditClient | None = None

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "reddit"

    def _get_client(self) -> RedditClient:
        """Get or create the Reddit client."""
        if self._client is None:
            if not settings.reddit_client_id or not settings.reddit_client_secret:
                raise RedditCredentialsMissingError(
                    "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set"
                )
            self._client = RedditClient(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )
        return self._client

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
            subreddits=subreddits,  # type: ignore[arg-type]
            time_filter=time_filter,  # type: ignore[arg-type]
            count=count,
            client=self._get_client(),
        )

    async def health_check(self) -> bool:
        """Check if Reddit is configured and available."""
        if not settings.reddit_client_id or not settings.reddit_client_secret:
            return False

        try:
            client = self._get_client()
            await client._get_token()
            return True
        except RedditError:
            return False


# Convenience instance
reddit_source = RedditSource()
