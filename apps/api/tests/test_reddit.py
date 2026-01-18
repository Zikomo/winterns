"""Tests for Reddit data source."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from wintern.sources.reddit import (
    REDDIT_AUTH_URL,
    REDDIT_SEARCH_URL,
    REDDIT_SUBREDDIT_SEARCH_URL,
    RedditAPIError,
    RedditAuthError,
    RedditClient,
    RedditCredentialsMissingError,
    RedditError,
    RedditRateLimitError,
    RedditSource,
    _parse_created_utc,
    search_reddit,
)


class TestParseCreatedUtc:
    """Tests for _parse_created_utc helper."""

    def test_parse_valid_timestamp(self) -> None:
        """Test parsing a valid Unix timestamp."""
        timestamp = 1704067200.0  # 2024-01-01 00:00:00 UTC
        result = _parse_created_utc(timestamp)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.tzinfo == UTC

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        assert _parse_created_utc(None) is None

    def test_parse_invalid_timestamp(self) -> None:
        """Test parsing invalid timestamp returns None."""
        # Timestamp too large
        result = _parse_created_utc(float("inf"))
        assert result is None


class TestRedditClient:
    """Tests for RedditClient class."""

    def test_init(self) -> None:
        """Test client initialization."""
        client = RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
        )

        assert client.client_id == "test_id"
        assert client.client_secret == "test_secret"
        assert client.user_agent == "test_agent"
        assert client._token is None
        assert client._token_expires is None

    @pytest.mark.asyncio
    async def test_get_token_success(self) -> None:
        """Test successful token retrieval."""
        client = RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            token = await client._get_token()

            assert token == "test_token"
            assert client._token == "test_token"
            assert client._token_expires is not None

    @pytest.mark.asyncio
    async def test_get_token_uses_cache(self) -> None:
        """Test that cached token is returned when valid."""
        client = RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
        )

        # Set up cached token
        client._token = "cached_token"
        client._token_expires = datetime.now(UTC) + timedelta(hours=1)

        # Should return cached token without making request
        token = await client._get_token()
        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_token_refreshes_expired(self) -> None:
        """Test that expired token triggers refresh."""
        client = RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
        )

        # Set up expired token
        client._token = "old_token"
        client._token_expires = datetime.now(UTC) - timedelta(hours=1)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            token = await client._get_token()
            assert token == "new_token"

    @pytest.mark.asyncio
    async def test_get_token_auth_failure(self) -> None:
        """Test authentication failure."""
        client = RedditClient(
            client_id="bad_id",
            client_secret="bad_secret",
            user_agent="test_agent",
        )

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(RedditAuthError, match="Invalid Reddit credentials"):
                await client._get_token()

    def test_clear_token(self) -> None:
        """Test clearing the cached token."""
        client = RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
        )

        client._token = "test_token"
        client._token_expires = datetime.now(UTC) + timedelta(hours=1)

        client.clear_token()

        assert client._token is None
        assert client._token_expires is None


class TestSearchReddit:
    """Tests for search_reddit function."""

    @pytest.mark.asyncio
    async def test_missing_credentials(self) -> None:
        """Test error when credentials are missing."""
        with patch("wintern.sources.reddit.settings") as mock_settings:
            mock_settings.reddit_client_id = ""
            mock_settings.reddit_client_secret = ""

            with pytest.raises(
                RedditCredentialsMissingError,
                match="REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET",
            ):
                await search_reddit("test query")

    @pytest.mark.asyncio
    async def test_successful_search(self) -> None:
        """Test successful search returns results."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Test Post",
                            "selftext": "Test content here",
                            "permalink": "/r/test/comments/abc123/test_post/",
                            "subreddit": "test",
                            "author": "testuser",
                            "score": 100,
                            "num_comments": 50,
                            "is_self": True,
                            "domain": "self.test",
                            "created_utc": 1704067200.0,
                        }
                    }
                ]
            }
        }
        mock_search_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(return_value=mock_search_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test query")

            assert len(results) == 1
            assert results[0].title == "Test Post"
            assert results[0].snippet == "Test content here"
            assert results[0].source == "reddit"
            assert "subreddit" in results[0].metadata
            assert results[0].metadata["subreddit"] == "test"

    @pytest.mark.asyncio
    async def test_search_with_subreddits(self) -> None:
        """Test search within specific subreddits."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {"data": {"children": []}}
        mock_search_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(return_value=mock_search_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await search_reddit("test", subreddits=["python", "programming"])

            # Verify correct URL was used
            call_args = mock_client.get.call_args
            url = call_args[1].get("url") or call_args[0][0]
            assert "python+programming" in url

    @pytest.mark.asyncio
    async def test_search_skips_removed_posts(self) -> None:
        """Test that removed posts are skipped."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Removed Post",
                            "selftext": "",
                            "permalink": "/r/test/comments/abc123/",
                            "removed_by_category": "moderator",
                        }
                    },
                    {
                        "data": {
                            "title": "Valid Post",
                            "selftext": "Content",
                            "permalink": "/r/test/comments/def456/",
                        }
                    },
                ]
            }
        }
        mock_search_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(return_value=mock_search_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test")

            assert len(results) == 1
            assert results[0].title == "Valid Post"

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self) -> None:
        """Test handling of rate limit responses."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_rate_limit_response = MagicMock()
        mock_rate_limit_response.status_code = 429
        mock_rate_limit_response.headers = {"Retry-After": "1"}

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": {"children": []}}
        mock_success_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.reddit.asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(
                side_effect=[mock_rate_limit_response, mock_success_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test", max_retries=2)
            assert results == []

    @pytest.mark.asyncio
    async def test_server_error_retry(self) -> None:
        """Test retry on server errors."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": {"children": []}}
        mock_success_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.reddit.asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(side_effect=[mock_error_response, mock_success_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test", max_retries=2)
            assert results == []

    @pytest.mark.asyncio
    async def test_token_refresh_on_401(self) -> None:
        """Test token refresh when 401 received during search."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_401_response = MagicMock()
        mock_401_response.status_code = 401

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": {"children": []}}
        mock_success_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(side_effect=[mock_401_response, mock_success_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test", max_retries=2)
            assert results == []

    @pytest.mark.asyncio
    async def test_count_clamping(self) -> None:
        """Test that count is clamped to valid range."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {"data": {"children": []}}
        mock_search_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(return_value=mock_search_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Test count > 100
            await search_reddit("test", count=200)
            call_args = mock_client.get.call_args
            params = call_args[1]["params"]
            assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_timeout_error_retry(self) -> None:
        """Test retry on timeout errors."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": {"children": []}}
        mock_success_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.reddit.asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(
                side_effect=[httpx.TimeoutException("Timeout"), mock_success_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            results = await search_reddit("test", max_retries=2)
            assert results == []

    @pytest.mark.asyncio
    async def test_retries_exhausted(self) -> None:
        """Test error raised when retries are exhausted."""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.reddit.asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_auth_response)
            mock_client.get = AsyncMock(return_value=mock_error_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(RedditAPIError, match="Server error"):
                await search_reddit("test", max_retries=2)


class TestRedditSource:
    """Tests for RedditSource class."""

    def test_source_name(self) -> None:
        """Test source name property."""
        source = RedditSource()
        assert source.source_name == "reddit"

    @pytest.mark.asyncio
    async def test_search_delegates_to_search_reddit(self) -> None:
        """Test that search method delegates to search_reddit."""
        source = RedditSource()

        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            with patch("wintern.sources.reddit.settings") as mock_settings:
                mock_settings.reddit_client_id = "test_id"
                mock_settings.reddit_client_secret = "test_secret"
                mock_settings.reddit_user_agent = "test_agent"

                await source.search("test query", count=10)

                mock_search.assert_called_once()
                call_kwargs = mock_search.call_args[1]
                assert call_kwargs["count"] == 10

    @pytest.mark.asyncio
    async def test_search_with_time_filter(self) -> None:
        """Test search with time filter parameter."""
        source = RedditSource()

        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            with patch("wintern.sources.reddit.settings") as mock_settings:
                mock_settings.reddit_client_id = "test_id"
                mock_settings.reddit_client_secret = "test_secret"
                mock_settings.reddit_user_agent = "test_agent"

                await source.search("test", time_filter="month")

                call_kwargs = mock_search.call_args[1]
                assert call_kwargs["time_filter"] == "month"

    @pytest.mark.asyncio
    async def test_search_with_invalid_time_filter(self) -> None:
        """Test search with invalid time filter defaults to week."""
        source = RedditSource()

        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            with patch("wintern.sources.reddit.settings") as mock_settings:
                mock_settings.reddit_client_id = "test_id"
                mock_settings.reddit_client_secret = "test_secret"
                mock_settings.reddit_user_agent = "test_agent"

                await source.search("test", time_filter="invalid")

                call_kwargs = mock_search.call_args[1]
                assert call_kwargs["time_filter"] == "week"

    @pytest.mark.asyncio
    async def test_search_with_subreddits(self) -> None:
        """Test search with subreddits parameter."""
        source = RedditSource()

        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            with patch("wintern.sources.reddit.settings") as mock_settings:
                mock_settings.reddit_client_id = "test_id"
                mock_settings.reddit_client_secret = "test_secret"
                mock_settings.reddit_user_agent = "test_agent"

                await source.search("test", subreddits=["python", "programming"])

                call_kwargs = mock_search.call_args[1]
                assert call_kwargs["subreddits"] == ["python", "programming"]

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test health check when credentials are valid."""
        source = RedditSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_missing_credentials(self) -> None:
        """Test health check when credentials are missing."""
        source = RedditSource()

        with patch("wintern.sources.reddit.settings") as mock_settings:
            mock_settings.reddit_client_id = ""
            mock_settings.reddit_client_secret = ""

            result = await source.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(self) -> None:
        """Test health check when authentication fails."""
        source = RedditSource()

        mock_response = MagicMock()
        mock_response.status_code = 401

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.reddit_client_id = "bad_id"
            mock_settings.reddit_client_secret = "bad_secret"
            mock_settings.reddit_user_agent = "test_agent"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await source.health_check()
            assert result is False


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_reddit_error_is_base(self) -> None:
        """Test RedditError is the base exception."""
        assert issubclass(RedditCredentialsMissingError, RedditError)
        assert issubclass(RedditAuthError, RedditError)
        assert issubclass(RedditRateLimitError, RedditError)
        assert issubclass(RedditAPIError, RedditError)

    def test_reddit_api_error_has_status_code(self) -> None:
        """Test RedditAPIError includes status code."""
        error = RedditAPIError(503, "Service unavailable")
        assert error.status_code == 503
        assert "503" in str(error)
        assert "Service unavailable" in str(error)


class TestUrlConstants:
    """Tests for URL constants."""

    def test_auth_url(self) -> None:
        """Test auth URL is correct."""
        assert REDDIT_AUTH_URL == "https://www.reddit.com/api/v1/access_token"

    def test_search_url(self) -> None:
        """Test search URL is correct."""
        assert REDDIT_SEARCH_URL == "https://oauth.reddit.com/search"

    def test_subreddit_search_url(self) -> None:
        """Test subreddit search URL template is correct."""
        assert REDDIT_SUBREDDIT_SEARCH_URL == "https://oauth.reddit.com/r/{subreddit}/search"
