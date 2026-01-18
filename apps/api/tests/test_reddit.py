"""Tests for Reddit data source using AsyncPRAW."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asyncprawcore.exceptions import Forbidden, NotFound, ResponseException

from wintern.sources.reddit import (
    RedditAPIError,
    RedditAuthError,
    RedditCredentialsMissingError,
    RedditError,
    RedditSource,
    _create_reddit_client,
    _submission_to_search_result,
    search_reddit,
)


class TestCreateRedditClient:
    """Tests for _create_reddit_client helper."""

    def test_missing_client_id(self) -> None:
        """Test error when client_id is missing."""
        with patch("wintern.sources.reddit.settings") as mock_settings:
            mock_settings.reddit_client_id = ""
            mock_settings.reddit_client_secret = "secret"

            with pytest.raises(
                RedditCredentialsMissingError,
                match="REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET",
            ):
                _create_reddit_client()

    def test_missing_client_secret(self) -> None:
        """Test error when client_secret is missing."""
        with patch("wintern.sources.reddit.settings") as mock_settings:
            mock_settings.reddit_client_id = "client_id"
            mock_settings.reddit_client_secret = ""

            with pytest.raises(
                RedditCredentialsMissingError,
                match="REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET",
            ):
                _create_reddit_client()

    def test_creates_client_with_credentials(self) -> None:
        """Test client is created with proper credentials."""
        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit.asyncpraw.Reddit") as mock_reddit,
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "test_agent"

            _create_reddit_client()

            mock_reddit.assert_called_once_with(
                client_id="test_id",
                client_secret="test_secret",
                user_agent="test_agent",
            )


class TestSubmissionToSearchResult:
    """Tests for _submission_to_search_result helper."""

    def test_converts_submission(self) -> None:
        """Test converting a submission to SearchResult."""
        submission = MagicMock()
        submission.title = "Test Title"
        submission.selftext = "Test content here"
        submission.permalink = "/r/test/comments/abc123/test_title/"
        submission.subreddit = MagicMock(__str__=lambda s: "test")
        submission.author = MagicMock(__str__=lambda s: "testuser")
        submission.score = 100
        submission.num_comments = 50
        submission.is_self = True
        submission.domain = "self.test"
        submission.created_utc = 1704067200.0  # 2024-01-01 00:00:00 UTC

        result = _submission_to_search_result(submission)

        assert result.title == "Test Title"
        assert result.snippet == "Test content here"
        assert result.url == "https://www.reddit.com/r/test/comments/abc123/test_title/"
        assert result.source == "reddit"
        assert result.metadata["subreddit"] == "test"
        assert result.metadata["author"] == "testuser"
        assert result.metadata["score"] == 100
        assert result.published_at is not None
        assert result.published_at.year == 2024

    def test_handles_deleted_author(self) -> None:
        """Test handling deleted author."""
        submission = MagicMock()
        submission.title = "Test"
        submission.selftext = ""
        submission.permalink = "/r/test/comments/abc/"
        submission.subreddit = MagicMock(__str__=lambda s: "test")
        submission.author = None
        submission.score = 0
        submission.num_comments = 0
        submission.is_self = True
        submission.created_utc = None

        result = _submission_to_search_result(submission)

        assert result.metadata["author"] == "[deleted]"
        assert result.published_at is None

    def test_uses_title_as_snippet_when_no_selftext(self) -> None:
        """Test using title as snippet when selftext is empty."""
        submission = MagicMock()
        submission.title = "This is the title"
        submission.selftext = ""
        submission.permalink = "/r/test/comments/abc/"
        submission.subreddit = MagicMock(__str__=lambda s: "test")
        submission.author = MagicMock(__str__=lambda s: "user")
        submission.score = 0
        submission.num_comments = 0
        submission.is_self = False
        submission.domain = "example.com"
        submission.created_utc = None

        result = _submission_to_search_result(submission)

        assert result.snippet == "This is the title"


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
        mock_submission = MagicMock()
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Test content"
        mock_submission.permalink = "/r/test/comments/abc/"
        mock_submission.subreddit = MagicMock(__str__=lambda s: "test")
        mock_submission.author = MagicMock(__str__=lambda s: "user")
        mock_submission.score = 100
        mock_submission.num_comments = 10
        mock_submission.is_self = True
        mock_submission.domain = "self.test"
        mock_submission.created_utc = 1704067200.0
        mock_submission.removed_by_category = None

        mock_subreddit = AsyncMock()

        async def mock_search_generator(*args, **kwargs):
            yield mock_submission

        mock_subreddit.search = mock_search_generator

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            results = await search_reddit("test query")

            assert len(results) == 1
            assert results[0].title == "Test Post"
            assert results[0].source == "reddit"
            mock_reddit.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_subreddits(self) -> None:
        """Test search within specific subreddits."""
        mock_subreddit = AsyncMock()

        async def mock_search_generator(*args, **kwargs):
            return
            yield  # Make it an async generator

        mock_subreddit.search = mock_search_generator

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            await search_reddit("test", subreddits=["python", "programming"])

            # Verify subreddit was called with joined string
            mock_reddit.subreddit.assert_called_with("python+programming")

    @pytest.mark.asyncio
    async def test_search_all_reddit(self) -> None:
        """Test search across all of Reddit."""
        mock_subreddit = AsyncMock()

        async def mock_search_generator(*args, **kwargs):
            return
            yield

        mock_subreddit.search = mock_search_generator

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            await search_reddit("test")

            mock_reddit.subreddit.assert_called_with("all")

    @pytest.mark.asyncio
    async def test_skips_removed_posts(self) -> None:
        """Test that removed posts are skipped."""
        mock_removed = MagicMock()
        mock_removed.removed_by_category = "moderator"

        mock_valid = MagicMock()
        mock_valid.title = "Valid Post"
        mock_valid.selftext = "Content"
        mock_valid.permalink = "/r/test/comments/def/"
        mock_valid.subreddit = MagicMock(__str__=lambda s: "test")
        mock_valid.author = MagicMock(__str__=lambda s: "user")
        mock_valid.score = 50
        mock_valid.num_comments = 5
        mock_valid.is_self = True
        mock_valid.domain = "self.test"
        mock_valid.created_utc = None
        mock_valid.removed_by_category = None

        mock_subreddit = AsyncMock()

        async def mock_search_generator(*args, **kwargs):
            yield mock_removed
            yield mock_valid

        mock_subreddit.search = mock_search_generator

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            results = await search_reddit("test")

            assert len(results) == 1
            assert results[0].title == "Valid Post"

    @pytest.mark.asyncio
    async def test_forbidden_error(self) -> None:
        """Test handling of forbidden errors."""
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(side_effect=Forbidden(MagicMock()))
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            with pytest.raises(RedditAuthError, match="Access forbidden"):
                await search_reddit("test")

    @pytest.mark.asyncio
    async def test_not_found_error(self) -> None:
        """Test handling of not found errors."""
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(side_effect=NotFound(MagicMock()))
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            with pytest.raises(RedditAPIError, match="Resource not found"):
                await search_reddit("test")

    @pytest.mark.asyncio
    async def test_response_error(self) -> None:
        """Test handling of response errors."""
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(side_effect=ResponseException(MagicMock()))
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            with pytest.raises(RedditAPIError, match="Response error"):
                await search_reddit("test")

    @pytest.mark.asyncio
    async def test_count_clamping(self) -> None:
        """Test that count is clamped to valid range."""
        mock_subreddit = AsyncMock()

        async def mock_search_generator(*args, **kwargs):
            # Verify limit was clamped
            assert kwargs.get("limit") == 100
            return
            yield

        mock_subreddit.search = mock_search_generator

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = MagicMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            await search_reddit("test", count=200)


class TestRedditSource:
    """Tests for RedditSource class."""

    def test_source_name(self) -> None:
        """Test source name property."""
        source = RedditSource()
        assert source.source_name == "reddit"

    @pytest.mark.asyncio
    async def test_search_delegates_to_search_reddit(self) -> None:
        """Test that search method delegates to search_reddit."""
        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            source = RedditSource()
            await source.search("test query", count=10)

            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["count"] == 10

    @pytest.mark.asyncio
    async def test_search_with_time_filter(self) -> None:
        """Test search with time filter parameter."""
        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            source = RedditSource()
            await source.search("test", time_filter="month")

            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["time_filter"] == "month"

    @pytest.mark.asyncio
    async def test_search_with_invalid_time_filter(self) -> None:
        """Test search with invalid time filter defaults to week."""
        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            source = RedditSource()
            await source.search("test", time_filter="invalid")

            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["time_filter"] == "week"

    @pytest.mark.asyncio
    async def test_search_with_subreddits(self) -> None:
        """Test search with subreddits parameter."""
        with patch("wintern.sources.reddit.search_reddit") as mock_search:
            mock_search.return_value = []

            source = RedditSource()
            await source.search("test", subreddits=["python", "programming"])

            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["subreddits"] == ["python", "programming"]

    @pytest.mark.asyncio
    async def test_health_check_missing_credentials(self) -> None:
        """Test health check when credentials are missing."""
        with patch("wintern.sources.reddit.settings") as mock_settings:
            mock_settings.reddit_client_id = ""
            mock_settings.reddit_client_secret = ""

            source = RedditSource()
            result = await source.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test health check when credentials are valid."""
        mock_user = MagicMock()
        mock_user.me = AsyncMock(return_value=None)  # App-only auth returns None

        mock_reddit = AsyncMock()
        mock_reddit.user = mock_user
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"

            source = RedditSource()
            result = await source.health_check()

            assert result is True
            mock_reddit.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(self) -> None:
        """Test health check when authentication fails."""
        mock_user = MagicMock()
        mock_user.me = AsyncMock(side_effect=Forbidden(MagicMock()))

        mock_reddit = AsyncMock()
        mock_reddit.user = mock_user
        mock_reddit.close = AsyncMock()

        with (
            patch("wintern.sources.reddit.settings") as mock_settings,
            patch("wintern.sources.reddit._create_reddit_client", return_value=mock_reddit),
        ):
            mock_settings.reddit_client_id = "bad_id"
            mock_settings.reddit_client_secret = "bad_secret"

            source = RedditSource()
            result = await source.health_check()

            assert result is False


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_reddit_error_is_base(self) -> None:
        """Test RedditError is the base exception."""
        assert issubclass(RedditCredentialsMissingError, RedditError)
        assert issubclass(RedditAuthError, RedditError)
        assert issubclass(RedditAPIError, RedditError)

    def test_reddit_api_error_message(self) -> None:
        """Test RedditAPIError includes message."""
        error = RedditAPIError("Something went wrong")
        assert "Reddit API error" in str(error)
        assert "Something went wrong" in str(error)
