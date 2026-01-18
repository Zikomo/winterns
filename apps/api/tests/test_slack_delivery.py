"""Tests for the Slack delivery channel."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wintern.delivery import (
    DeliveryItem,
    DeliveryPayload,
    DeliveryResult,
    SlackDelivery,
    SlackError,
    SlackRateLimitError,
    SlackWebhookError,
    SlackWebhookMissingError,
    send_slack,
    slack_delivery,
)
from wintern.delivery.slack import (
    MAX_ITEMS_PER_MESSAGE,
    _build_blocks,
    _escape_mrkdwn_text,
    _escape_mrkdwn_url,
    _format_item_block,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_item() -> DeliveryItem:
    """Create a sample delivery item for testing."""
    return DeliveryItem(
        url="https://example.com/article",
        title="Test Article Title",
        relevance_score=85,
        reasoning="Highly relevant to the research topic.",
        key_excerpt="This is a key excerpt from the article.",
    )


@pytest.fixture
def sample_payload(sample_item: DeliveryItem) -> DeliveryPayload:
    """Create a sample delivery payload for testing."""
    return DeliveryPayload(
        subject="Weekly Research Digest",
        body="Here are the top articles from this week.",
        items=[sample_item],
    )


@pytest.fixture
def mock_webhook_response() -> MagicMock:
    """Create a mock webhook response."""
    response = MagicMock()
    response.status_code = 200
    response.body = "ok"
    return response


# -----------------------------------------------------------------------------
# Schema Tests
# -----------------------------------------------------------------------------


class TestDeliveryItem:
    """Tests for DeliveryItem schema."""

    def test_create_item(self) -> None:
        """Test creating a delivery item."""
        item = DeliveryItem(
            url="https://example.com",
            title="Test Title",
            relevance_score=75,
            reasoning="Test reasoning",
        )
        assert item.url == "https://example.com"
        assert item.title == "Test Title"
        assert item.relevance_score == 75
        assert item.reasoning == "Test reasoning"
        assert item.key_excerpt is None

    def test_item_with_excerpt(self) -> None:
        """Test creating an item with key excerpt."""
        item = DeliveryItem(
            url="https://example.com",
            title="Test Title",
            relevance_score=90,
            reasoning="Test reasoning",
            key_excerpt="Important quote from the article.",
        )
        assert item.key_excerpt == "Important quote from the article."

    def test_score_validation(self) -> None:
        """Test that relevance score is validated."""
        with pytest.raises(ValueError, match="less than or equal to 100"):
            DeliveryItem(
                url="https://example.com",
                title="Test",
                relevance_score=101,  # Invalid: > 100
                reasoning="Test",
            )

        with pytest.raises(ValueError, match="greater than or equal to 0"):
            DeliveryItem(
                url="https://example.com",
                title="Test",
                relevance_score=-1,  # Invalid: < 0
                reasoning="Test",
            )


class TestDeliveryPayload:
    """Tests for DeliveryPayload schema."""

    def test_create_payload(self, sample_item: DeliveryItem) -> None:
        """Test creating a delivery payload."""
        payload = DeliveryPayload(
            subject="Test Subject",
            body="Test body content",
            items=[sample_item],
        )
        assert payload.subject == "Test Subject"
        assert payload.body == "Test body content"
        assert len(payload.items) == 1

    def test_payload_empty_items(self) -> None:
        """Test creating a payload with no items."""
        payload = DeliveryPayload(
            subject="No Items",
            body="No content this week.",
        )
        assert payload.items == []


class TestDeliveryResult:
    """Tests for DeliveryResult schema."""

    def test_success_result(self) -> None:
        """Test creating a success result."""
        result = DeliveryResult(
            success=True,
            channel="slack",
        )
        assert result.success is True
        assert result.channel == "slack"
        assert result.error_message is None
        assert result.timestamp is not None

    def test_failure_result(self) -> None:
        """Test creating a failure result."""
        result = DeliveryResult(
            success=False,
            channel="slack",
            error_message="Webhook URL invalid",
        )
        assert result.success is False
        assert result.error_message == "Webhook URL invalid"


# -----------------------------------------------------------------------------
# Block Builder Tests
# -----------------------------------------------------------------------------


class TestEscapeMrkdwnText:
    """Tests for _escape_mrkdwn_text function (display text escaping)."""

    def test_escape_pipe(self) -> None:
        """Test that pipe characters are escaped."""
        result = _escape_mrkdwn_text("Hello | World")
        assert "|" not in result
        assert "\u2223" in result  # Unicode DIVIDES character

    def test_escape_angle_brackets(self) -> None:
        """Test that angle brackets are escaped."""
        result = _escape_mrkdwn_text("<tag>content</tag>")
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_escape_ampersand(self) -> None:
        """Test that ampersands are escaped."""
        result = _escape_mrkdwn_text("A & B")
        assert "&amp;" in result

    def test_escape_order(self) -> None:
        """Test that ampersands are escaped before other entities."""
        # This ensures we don't double-escape &lt; to &amp;lt;
        result = _escape_mrkdwn_text("A & B < C")
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&amp;lt;" not in result

    def test_no_escape_needed(self) -> None:
        """Test that clean text passes through unchanged."""
        result = _escape_mrkdwn_text("Hello World")
        assert result == "Hello World"


class TestEscapeMrkdwnUrl:
    """Tests for _escape_mrkdwn_url function (URL escaping)."""

    def test_escape_pipe_in_url(self) -> None:
        """Test that pipe characters in URLs are URL-encoded."""
        result = _escape_mrkdwn_url("https://example.com/path?a=1|2")
        assert "|" not in result
        assert "%7C" in result

    def test_escape_greater_than_in_url(self) -> None:
        """Test that > characters in URLs are URL-encoded."""
        result = _escape_mrkdwn_url("https://example.com/path?redirect=>next")
        assert ">" not in result
        assert "%3E" in result

    def test_escape_both_pipe_and_gt(self) -> None:
        """Test escaping both pipe and > in the same URL."""
        result = _escape_mrkdwn_url("https://example.com/?a|b>c")
        assert "|" not in result
        assert ">" not in result
        assert "%7C" in result
        assert "%3E" in result

    def test_no_escape_needed(self) -> None:
        """Test that clean URLs pass through unchanged."""
        url = "https://example.com/article?id=123&category=tech"
        result = _escape_mrkdwn_url(url)
        assert result == url

    def test_preserves_other_url_encoded_chars(self) -> None:
        """Test that existing URL encoding is preserved."""
        url = "https://example.com/search?q=hello%20world"
        result = _escape_mrkdwn_url(url)
        assert result == url


class TestFormatItemBlock:
    """Tests for _format_item_block function."""

    def test_format_high_score_item(self, sample_item: DeliveryItem) -> None:
        """Test formatting a high-score item (green emoji)."""
        block = _format_item_block(sample_item, 1)
        assert block["type"] == "section"
        assert "🟢" in block["text"]["text"]
        assert sample_item.title in block["text"]["text"]
        assert sample_item.url in block["text"]["text"]

    def test_format_medium_score_item(self) -> None:
        """Test formatting a medium-score item (yellow emoji)."""
        item = DeliveryItem(
            url="https://example.com",
            title="Medium Article",
            relevance_score=65,
            reasoning="Somewhat relevant.",
        )
        block = _format_item_block(item, 2)
        assert "🟡" in block["text"]["text"]

    def test_format_low_score_item(self) -> None:
        """Test formatting a low-score item (red emoji)."""
        item = DeliveryItem(
            url="https://example.com",
            title="Low Article",
            relevance_score=45,
            reasoning="Not very relevant.",
        )
        block = _format_item_block(item, 3)
        assert "🔴" in block["text"]["text"]

    def test_format_item_with_long_excerpt(self) -> None:
        """Test that long excerpts are truncated."""
        long_excerpt = "x" * 300
        item = DeliveryItem(
            url="https://example.com",
            title="Test",
            relevance_score=85,
            reasoning="Test",
            key_excerpt=long_excerpt,
        )
        block = _format_item_block(item, 1)
        # Should be truncated to 200 chars + "..."
        assert "..." in block["text"]["text"]

    def test_format_item_escapes_special_chars_in_title(self) -> None:
        """Test that special characters in title are escaped for mrkdwn."""
        item = DeliveryItem(
            url="https://example.com",
            title="Title with | pipe & <brackets>",
            relevance_score=85,
            reasoning="Test",
        )
        block = _format_item_block(item, 1)
        text = block["text"]["text"]
        # The original title had a pipe - check it was escaped to unicode DIVIDES
        assert "\u2223" in text  # Escaped pipe (unicode DIVIDES)
        assert "&amp;" in text  # Escaped ampersand
        assert "&lt;" in text  # Escaped <
        assert "&gt;" in text  # Escaped >

    def test_format_item_escapes_special_chars_in_url(self) -> None:
        """Test that special characters in URLs are URL-encoded for mrkdwn."""
        item = DeliveryItem(
            url="https://example.com/article?filter=a|b&redirect=>next",
            title="Test Article",
            relevance_score=85,
            reasoning="Test",
        )
        block = _format_item_block(item, 1)
        text = block["text"]["text"]
        # The URL should have pipe and > URL-encoded
        assert "%7C" in text  # URL-encoded pipe
        assert "%3E" in text  # URL-encoded >
        # Original characters should not appear in URL portion of the link
        # Note: the link format is <url|title>, so we check the escaped URL is there
        assert "https://example.com/article?filter=a%7Cb&redirect=%3Enext" in text


class TestBuildBlocks:
    """Tests for _build_blocks function."""

    def test_build_blocks_basic(self, sample_payload: DeliveryPayload) -> None:
        """Test building blocks from a basic payload."""
        blocks = _build_blocks(sample_payload)

        # Should have: header, divider, body, divider, item, timestamp
        assert len(blocks) >= 5
        assert blocks[0]["type"] == "header"
        assert blocks[1]["type"] == "divider"

    def test_build_blocks_truncates_items(self) -> None:
        """Test that items are truncated at MAX_ITEMS_PER_MESSAGE."""
        items = [
            DeliveryItem(
                url=f"https://example.com/{i}",
                title=f"Article {i}",
                relevance_score=80,
                reasoning=f"Reason {i}",
            )
            for i in range(15)  # More than MAX_ITEMS_PER_MESSAGE
        ]
        payload = DeliveryPayload(
            subject="Many Items",
            body="",
            items=items,
        )
        blocks = _build_blocks(payload)

        # Count section blocks (items)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) == MAX_ITEMS_PER_MESSAGE

        # Should have a context block mentioning remaining items
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert any("more items" in str(b) for b in context_blocks)

    def test_build_blocks_truncates_long_subject(self) -> None:
        """Test that long subjects are truncated."""
        long_subject = "x" * 200
        payload = DeliveryPayload(
            subject=long_subject,
            body="Test",
            items=[],
        )
        blocks = _build_blocks(payload)
        header = blocks[0]
        assert len(header["text"]["text"]) <= 150


# -----------------------------------------------------------------------------
# send_slack Function Tests
# -----------------------------------------------------------------------------


class TestSendSlack:
    """Tests for send_slack function."""

    @pytest.mark.asyncio
    async def test_send_slack_success(
        self,
        sample_payload: DeliveryPayload,
        mock_webhook_response: MagicMock,
    ) -> None:
        """Test successful message send."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_webhook_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            result = await send_slack(
                "https://hooks.slack.com/services/xxx",
                sample_payload,
            )

            assert result is True
            mock_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_missing_url(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test that empty webhook URL raises error."""
        with pytest.raises(SlackWebhookMissingError):
            await send_slack("", sample_payload)

    @pytest.mark.asyncio
    async def test_send_slack_rate_limit(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test rate limit handling."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.body = "rate_limited"

            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            with pytest.raises(SlackRateLimitError):
                await send_slack(
                    "https://hooks.slack.com/services/xxx",
                    sample_payload,
                )

    @pytest.mark.asyncio
    async def test_send_slack_error_response(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test handling of error response."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.body = "invalid_payload"

            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            with pytest.raises(SlackWebhookError) as exc_info:
                await send_slack(
                    "https://hooks.slack.com/services/xxx",
                    sample_payload,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_send_slack_network_error(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test that network errors are wrapped in SlackWebhookError."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.send = AsyncMock(side_effect=ConnectionError("Network unreachable"))
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            with pytest.raises(SlackWebhookError, match="Network or client error"):
                await send_slack(
                    "https://hooks.slack.com/services/xxx",
                    sample_payload,
                )


# -----------------------------------------------------------------------------
# SlackDelivery Class Tests
# -----------------------------------------------------------------------------


class TestSlackDelivery:
    """Tests for SlackDelivery class."""

    def test_channel_name(self) -> None:
        """Test that channel name is 'slack'."""
        delivery = SlackDelivery()
        assert delivery.channel_name == "slack"

    def test_custom_webhook_url(self) -> None:
        """Test using custom webhook URL."""
        custom_url = "https://hooks.slack.com/custom"
        delivery = SlackDelivery(webhook_url=custom_url)
        assert delivery.webhook_url == custom_url

    def test_default_webhook_url(self) -> None:
        """Test falling back to settings for webhook URL."""
        with patch("wintern.delivery.slack.settings") as mock_settings:
            mock_settings.slack_default_webhook_url = "https://hooks.slack.com/default"
            delivery = SlackDelivery()
            assert delivery.webhook_url == "https://hooks.slack.com/default"

    @pytest.mark.asyncio
    async def test_deliver_success(
        self,
        sample_payload: DeliveryPayload,
        mock_webhook_response: MagicMock,
    ) -> None:
        """Test successful delivery."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_webhook_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            delivery = SlackDelivery(webhook_url="https://hooks.slack.com/test")
            result = await delivery.deliver(sample_payload)

            assert isinstance(result, DeliveryResult)
            assert result.success is True
            assert result.channel == "slack"
            assert result.error_message is None

    @pytest.mark.asyncio
    async def test_deliver_failure(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test delivery failure handling."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.body = "server_error"

            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            delivery = SlackDelivery(webhook_url="https://hooks.slack.com/test")
            result = await delivery.deliver(sample_payload)

            assert result.success is False
            assert result.channel == "slack"
            assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_deliver_with_url_override(
        self,
        sample_payload: DeliveryPayload,
        mock_webhook_response: MagicMock,
    ) -> None:
        """Test delivery with webhook URL override in kwargs."""
        with patch("wintern.delivery.slack.AsyncWebhookClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.send = AsyncMock(return_value=mock_webhook_response)
            mock_client.retry_handlers = []
            mock_client_class.return_value = mock_client

            delivery = SlackDelivery(webhook_url="https://hooks.slack.com/default")
            await delivery.deliver(
                sample_payload,
                webhook_url="https://hooks.slack.com/override",
            )

            # Verify the override URL was used
            mock_client_class.assert_called_with(url="https://hooks.slack.com/override")

    @pytest.mark.asyncio
    async def test_deliver_unexpected_error(
        self,
        sample_payload: DeliveryPayload,
    ) -> None:
        """Test that unexpected errors are caught and returned as failed result."""
        with patch("wintern.delivery.slack.send_slack") as mock_send:
            # Simulate an unexpected error that escapes send_slack
            mock_send.side_effect = RuntimeError("Unexpected internal error")

            delivery = SlackDelivery(webhook_url="https://hooks.slack.com/test")
            result = await delivery.deliver(sample_payload)

            assert result.success is False
            assert "Unexpected error" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_health_check_configured(self) -> None:
        """Test health check when webhook is configured."""
        delivery = SlackDelivery(webhook_url="https://hooks.slack.com/test")
        result = await delivery.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self) -> None:
        """Test health check when webhook is not configured."""
        with patch("wintern.delivery.slack.settings") as mock_settings:
            mock_settings.slack_default_webhook_url = ""
            delivery = SlackDelivery()
            result = await delivery.health_check()
            assert result is False


# -----------------------------------------------------------------------------
# Error Class Tests
# -----------------------------------------------------------------------------


class TestSlackErrors:
    """Tests for Slack error classes."""

    def test_slack_error_base(self) -> None:
        """Test base SlackError."""
        error = SlackError("Test error")
        assert str(error) == "Test error"

    def test_slack_webhook_missing_error(self) -> None:
        """Test SlackWebhookMissingError."""
        error = SlackWebhookMissingError("No URL")
        assert isinstance(error, SlackError)

    def test_slack_webhook_error(self) -> None:
        """Test SlackWebhookError with status code."""
        error = SlackWebhookError("Bad request", status_code=400)
        assert "Slack webhook error" in str(error)
        assert error.status_code == 400

    def test_slack_rate_limit_error(self) -> None:
        """Test SlackRateLimitError with retry_after."""
        error = SlackRateLimitError(retry_after=30)
        assert error.retry_after == 30
        assert "30s" in str(error)

    def test_slack_rate_limit_error_no_retry(self) -> None:
        """Test SlackRateLimitError without retry_after."""
        error = SlackRateLimitError()
        assert error.retry_after is None
        assert "Rate limited" in str(error)


# -----------------------------------------------------------------------------
# Module-level Instance Tests
# -----------------------------------------------------------------------------


class TestSlackDeliveryInstance:
    """Tests for the module-level slack_delivery instance."""

    def test_instance_exists(self) -> None:
        """Test that slack_delivery instance exists."""
        assert slack_delivery is not None
        assert isinstance(slack_delivery, SlackDelivery)

    def test_instance_channel_name(self) -> None:
        """Test that instance has correct channel name."""
        assert slack_delivery.channel_name == "slack"
