"""Tests for the Brave Search data source."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from wintern.sources.brave import (
    BraveAPIError,
    BraveAPIKeyMissingError,
    BraveRateLimitError,
    BraveSearchError,
    BraveSearchSource,
    _parse_age_to_datetime,
    _parse_retry_after,
    search_brave,
)
from wintern.sources.schemas import SearchResult

# -----------------------------------------------------------------------------
# SearchResult Model Tests
# -----------------------------------------------------------------------------


class TestSearchResult:
    """Tests for the SearchResult model."""

    def test_minimal_search_result(self):
        """Test creating a search result with required fields only."""
        result = SearchResult(
            url="https://example.com",
            title="Example Title",
            snippet="Example snippet text.",
            source="brave_search",
        )
        assert result.url == "https://example.com"
        assert result.title == "Example Title"
        assert result.snippet == "Example snippet text."
        assert result.source == "brave_search"
        assert result.published_at is None
        assert result.metadata == {}

    def test_full_search_result(self):
        """Test creating a search result with all fields."""
        now = datetime.now(UTC)
        result = SearchResult(
            url="https://example.com/article",
            title="Full Article",
            snippet="This is a full snippet.",
            source="brave_search",
            published_at=now,
            metadata={"language": "en", "family_friendly": True},
        )
        assert result.published_at == now
        assert result.metadata["language"] == "en"

    def test_to_scraped_item(self):
        """Test converting SearchResult to ScrapedItem format."""
        now = datetime.now(UTC)
        result = SearchResult(
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
            source="brave_search",
            published_at=now,
        )
        scraped = result.to_scraped_item()

        assert scraped["url"] == "https://example.com"
        assert scraped["title"] == "Test"
        assert scraped["snippet"] == "Test snippet"
        assert scraped["source"] == "brave_search"
        assert scraped["published_date"] == now.isoformat()

    def test_to_scraped_item_no_date(self):
        """Test converting SearchResult without published_at."""
        result = SearchResult(
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
            source="brave_search",
        )
        scraped = result.to_scraped_item()
        assert scraped["published_date"] is None


# -----------------------------------------------------------------------------
# Age Parsing Tests
# -----------------------------------------------------------------------------


class TestParseAgeToDatetime:
    """Tests for the _parse_age_to_datetime function."""

    def test_parse_hours(self):
        """Test parsing hours ago."""
        result = _parse_age_to_datetime("2 hours ago")
        assert result is not None
        assert datetime.now(UTC) - result < timedelta(hours=3)
        assert datetime.now(UTC) - result > timedelta(hours=1)

    def test_parse_days(self):
        """Test parsing days ago."""
        result = _parse_age_to_datetime("3 days ago")
        assert result is not None
        assert datetime.now(UTC) - result < timedelta(days=4)
        assert datetime.now(UTC) - result > timedelta(days=2)

    def test_parse_weeks(self):
        """Test parsing weeks ago."""
        result = _parse_age_to_datetime("2 weeks ago")
        assert result is not None
        assert datetime.now(UTC) - result < timedelta(weeks=3)
        assert datetime.now(UTC) - result > timedelta(weeks=1)

    def test_parse_months(self):
        """Test parsing months ago."""
        result = _parse_age_to_datetime("1 month ago")
        assert result is not None
        # Approximately 30 days
        assert datetime.now(UTC) - result < timedelta(days=45)
        assert datetime.now(UTC) - result > timedelta(days=15)

    def test_parse_years(self):
        """Test parsing years ago."""
        result = _parse_age_to_datetime("1 year ago")
        assert result is not None
        assert datetime.now(UTC) - result < timedelta(days=400)
        assert datetime.now(UTC) - result > timedelta(days=300)

    def test_parse_none(self):
        """Test parsing None returns None."""
        assert _parse_age_to_datetime(None) is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        assert _parse_age_to_datetime("") is None

    def test_parse_invalid_format(self):
        """Test parsing invalid format returns None."""
        assert _parse_age_to_datetime("invalid") is None
        assert _parse_age_to_datetime("not a date") is None


# -----------------------------------------------------------------------------
# Retry-After Parsing Tests
# -----------------------------------------------------------------------------


class TestParseRetryAfter:
    """Tests for the _parse_retry_after function."""

    def test_parse_integer_seconds(self):
        """Test parsing integer seconds."""
        assert _parse_retry_after("120") == 120
        assert _parse_retry_after("5") == 5
        assert _parse_retry_after("0") == 0

    def test_parse_none_returns_default(self):
        """Test that None returns the default value."""
        assert _parse_retry_after(None) == 5
        assert _parse_retry_after(None, default=10) == 10

    def test_parse_empty_string_returns_default(self):
        """Test that empty string returns the default value."""
        assert _parse_retry_after("") == 5
        assert _parse_retry_after("", default=15) == 15

    def test_parse_invalid_returns_default(self):
        """Test that invalid values return the default."""
        assert _parse_retry_after("not-a-number") == 5
        assert _parse_retry_after("abc123") == 5

    def test_parse_http_date(self):
        """Test parsing HTTP-date format."""
        # Create a date 60 seconds in the future
        from email.utils import format_datetime

        future = datetime.now(UTC) + timedelta(seconds=60)
        http_date = format_datetime(future, usegmt=True)
        result = _parse_retry_after(http_date)
        # Should be approximately 60 seconds (allow some tolerance)
        assert 55 <= result <= 65

    def test_parse_http_date_in_past_returns_minimum(self):
        """Test that HTTP-date in the past returns minimum of 1 second."""
        from email.utils import format_datetime

        past = datetime.now(UTC) - timedelta(seconds=60)
        http_date = format_datetime(past, usegmt=True)
        result = _parse_retry_after(http_date)
        assert result == 1  # Minimum of 1 second


# -----------------------------------------------------------------------------
# Brave Search Function Tests
# -----------------------------------------------------------------------------


class TestSearchBrave:
    """Tests for the search_brave function."""

    @pytest.mark.asyncio
    async def test_search_brave_success(self):
        """Test successful Brave search."""
        mock_response_data = {
            "web": {
                "results": [
                    {
                        "url": "https://example.com/article1",
                        "title": "First Article",
                        "description": "Description of first article.",
                        "age": "2 hours ago",
                        "language": "en",
                        "family_friendly": True,
                    },
                    {
                        "url": "https://example.com/article2",
                        "title": "Second Article",
                        "description": "Description of second article.",
                        "age": "1 day ago",
                    },
                ]
            }
        }

        # Use MagicMock for response since json() and raise_for_status() are sync
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await search_brave("test query", count=10)

            assert len(results) == 2
            assert results[0].url == "https://example.com/article1"
            assert results[0].title == "First Article"
            assert results[0].snippet == "Description of first article."
            assert results[0].source == "brave_search"
            assert results[0].published_at is not None
            assert results[0].metadata["language"] == "en"

    @pytest.mark.asyncio
    async def test_search_brave_no_api_key(self):
        """Test that missing API key raises appropriate error."""
        with patch("wintern.sources.brave.settings") as mock_settings:
            mock_settings.brave_api_key = ""

            with pytest.raises(BraveAPIKeyMissingError):
                await search_brave("test query")

    @pytest.mark.asyncio
    async def test_search_brave_with_freshness(self):
        """Test search with freshness filter."""
        mock_response_data = {"web": {"results": []}}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await search_brave("test query", freshness="pd")

            # Verify freshness was passed in params
            call_args = mock_client.get.call_args
            assert call_args.kwargs["params"]["freshness"] == "pd"

    @pytest.mark.asyncio
    async def test_search_brave_count_clamping(self):
        """Test that count is clamped to valid range."""
        mock_response_data = {"web": {"results": []}}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Test count > 20 gets clamped to 20
            await search_brave("test", count=100)
            call_args = mock_client.get.call_args
            assert call_args.kwargs["params"]["count"] == 20

            # Test count < 1 gets clamped to 1
            await search_brave("test", count=0)
            call_args = mock_client.get.call_args
            assert call_args.kwargs["params"]["count"] == 1

    @pytest.mark.asyncio
    async def test_search_brave_rate_limit_retry(self):
        """Test retry on rate limit."""
        mock_rate_limit_response = MagicMock()
        mock_rate_limit_response.status_code = 429
        mock_rate_limit_response.headers = {"Retry-After": "1"}

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"web": {"results": []}}

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.brave.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            # First call rate limited, second succeeds
            mock_client.get.side_effect = [
                mock_rate_limit_response,
                mock_success_response,
            ]
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await search_brave("test", max_retries=3)
            assert results == []
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_search_brave_server_error_retry(self):
        """Test retry on server error."""
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"web": {"results": []}}

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.brave.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.side_effect = [mock_error_response, mock_success_response]
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await search_brave("test", max_retries=3)
            assert results == []
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_search_brave_client_error_no_retry(self):
        """Test that client errors (4xx) don't retry."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        http_error = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = http_error

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(BraveAPIError) as exc_info:
                await search_brave("test", max_retries=3)

            assert exc_info.value.status_code == 400
            # Should only try once for client errors
            assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_search_brave_all_retries_exhausted(self):
        """Test error when all retries are exhausted."""
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.httpx.AsyncClient") as mock_client_class,
            patch("wintern.sources.brave._rate_limit", new_callable=AsyncMock),
            patch("wintern.sources.brave.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.brave_api_key = "test-api-key"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_error_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(BraveAPIError):
                await search_brave("test", max_retries=2)

            assert mock_client.get.call_count == 2


# -----------------------------------------------------------------------------
# BraveSearchSource Class Tests
# -----------------------------------------------------------------------------


class TestBraveSearchSource:
    """Tests for the BraveSearchSource class."""

    def test_source_name(self):
        """Test that source name is correct."""
        source = BraveSearchSource()
        assert source.source_name == "brave_search"

    @pytest.mark.asyncio
    async def test_search_method(self):
        """Test the search method delegates to search_brave."""
        with patch("wintern.sources.brave.search_brave") as mock_search:
            mock_search.return_value = [
                SearchResult(
                    url="https://example.com",
                    title="Test",
                    snippet="Test",
                    source="brave_search",
                )
            ]

            source = BraveSearchSource()
            results = await source.search("test query", count=5, freshness="pd")

            mock_search.assert_called_once_with("test query", count=5, freshness="pd")
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_method_invalid_freshness(self):
        """Test that invalid freshness values are filtered out."""
        with patch("wintern.sources.brave.search_brave") as mock_search:
            mock_search.return_value = []

            source = BraveSearchSource()
            await source.search("test", freshness="invalid")

            # Invalid freshness should be converted to None
            mock_search.assert_called_once_with("test", count=10, freshness=None)

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when API is available."""
        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.search_brave") as mock_search,
        ):
            mock_settings.brave_api_key = "test-key"
            mock_search.return_value = []

            source = BraveSearchSource()
            result = await source.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_no_api_key(self):
        """Test health check when API key is missing."""
        with patch("wintern.sources.brave.settings") as mock_settings:
            mock_settings.brave_api_key = ""

            source = BraveSearchSource()
            result = await source.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_api_error(self):
        """Test health check when API returns error."""
        with (
            patch("wintern.sources.brave.settings") as mock_settings,
            patch("wintern.sources.brave.search_brave") as mock_search,
        ):
            mock_settings.brave_api_key = "test-key"
            mock_search.side_effect = BraveAPIError(500, "Server error")

            source = BraveSearchSource()
            result = await source.health_check()

            assert result is False


# -----------------------------------------------------------------------------
# Exception Tests
# -----------------------------------------------------------------------------


class TestBraveExceptions:
    """Tests for Brave Search exceptions."""

    def test_brave_api_key_missing_error(self):
        """Test BraveAPIKeyMissingError."""
        error = BraveAPIKeyMissingError("API key not set")
        assert str(error) == "API key not set"
        assert isinstance(error, BraveSearchError)

    def test_brave_rate_limit_error(self):
        """Test BraveRateLimitError."""
        error = BraveRateLimitError("Rate limited")
        assert str(error) == "Rate limited"
        assert isinstance(error, BraveSearchError)

    def test_brave_api_error(self):
        """Test BraveAPIError."""
        error = BraveAPIError(500, "Internal server error")
        assert error.status_code == 500
        assert "500" in str(error)
        assert "Internal server error" in str(error)
        assert isinstance(error, BraveSearchError)
