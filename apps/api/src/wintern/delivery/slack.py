"""Slack delivery channel using slack-sdk AsyncWebhookClient."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler
from slack_sdk.webhook.async_client import AsyncWebhookClient

from wintern.core.config import settings
from wintern.delivery.base import DeliveryChannel
from wintern.delivery.schemas import DeliveryItem, DeliveryPayload, DeliveryResult

logger = logging.getLogger(__name__)

# Maximum number of items to include in a Slack message (Slack has block limits)
MAX_ITEMS_PER_MESSAGE = 10


class SlackError(Exception):
    """Base exception for Slack errors."""

    pass


class SlackWebhookMissingError(SlackError):
    """Raised when Slack webhook URL is not configured."""

    pass


class SlackWebhookError(SlackError):
    """Raised when webhook delivery fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(f"Slack webhook error: {message}")


class SlackRateLimitError(SlackError):
    """Raised when rate limited by Slack."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        message = "Rate limited by Slack"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message)


def _format_item_block(item: DeliveryItem, index: int) -> dict[str, Any]:
    """Format a single item as a Slack Block Kit section.

    Args:
        item: The delivery item to format.
        index: The 1-based index of the item.

    Returns:
        A Slack Block Kit section block.
    """
    # Build the item text with score indicator
    if item.relevance_score >= 80:
        score_emoji = "🟢"
    elif item.relevance_score >= 60:
        score_emoji = "🟡"
    else:
        score_emoji = "🔴"
    text_parts = [f"*{index}. <{item.url}|{item.title}>* {score_emoji}"]
    text_parts.append(f"_{item.reasoning}_")

    if item.key_excerpt:
        # Truncate excerpt if too long
        if len(item.key_excerpt) > 200:
            excerpt = item.key_excerpt[:200] + "..."
        else:
            excerpt = item.key_excerpt
        text_parts.append(f"> {excerpt}")

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(text_parts),
        },
    }


def _build_blocks(payload: DeliveryPayload) -> list[dict[str, Any]]:
    """Build Slack Block Kit blocks from a delivery payload.

    Args:
        payload: The delivery payload to format.

    Returns:
        A list of Slack Block Kit blocks.
    """
    blocks: list[dict[str, Any]] = [
        # Header
        {
            "type": "header",
            "text": {"type": "plain_text", "text": payload.subject[:150], "emoji": True},
        },
        {"type": "divider"},
    ]

    # Body section if present
    if payload.body:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.body[:3000]},
            }
        )
        blocks.append({"type": "divider"})

    # Add items (limit to MAX_ITEMS_PER_MESSAGE)
    items_to_show = payload.items[:MAX_ITEMS_PER_MESSAGE]
    for i, item in enumerate(items_to_show, 1):
        blocks.append(_format_item_block(item, i))

    # Add footer if items were truncated
    if len(payload.items) > MAX_ITEMS_PER_MESSAGE:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_...and {len(payload.items) - MAX_ITEMS_PER_MESSAGE} more items_",
                    }
                ],
            }
        )

    # Timestamp footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
                }
            ],
        }
    )

    return blocks


async def send_slack(
    webhook_url: str,
    payload: DeliveryPayload,
) -> bool:
    """Send a digest to Slack via incoming webhook.

    Args:
        webhook_url: The Slack incoming webhook URL.
        payload: The delivery payload to send.

    Returns:
        True if the message was sent successfully.

    Raises:
        SlackWebhookMissingError: If webhook URL is empty.
        SlackWebhookError: If the webhook request fails.
        SlackRateLimitError: If rate limited by Slack.
    """
    if not webhook_url:
        raise SlackWebhookMissingError("Slack webhook URL is required")

    # Create client with rate limit retry handler
    client = AsyncWebhookClient(url=webhook_url)
    rate_limit_handler = AsyncRateLimitErrorRetryHandler(max_retry_count=2)
    client.retry_handlers.append(rate_limit_handler)

    blocks = _build_blocks(payload)

    try:
        response = await client.send(
            text=payload.subject,  # Fallback text for notifications
            blocks=blocks,
        )

        if response.status_code == 200:
            logger.debug(f"Slack message sent successfully: {payload.subject}")
            return True

        if response.status_code == 429:
            raise SlackRateLimitError()

        raise SlackWebhookError(
            f"Unexpected response: {response.body}",
            status_code=response.status_code,
        )

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}")
        raise SlackWebhookError(str(e)) from e


class SlackDelivery(DeliveryChannel):
    """Slack delivery channel implementation using webhooks."""

    def __init__(self, webhook_url: str | None = None) -> None:
        """Initialize the Slack delivery channel.

        Args:
            webhook_url: Optional webhook URL override.
                Defaults to settings.slack_default_webhook_url.
        """
        self._webhook_url = webhook_url

    @property
    def webhook_url(self) -> str:
        """Get the configured webhook URL."""
        return self._webhook_url or settings.slack_default_webhook_url

    @property
    def channel_name(self) -> str:
        """Return the channel identifier."""
        return "slack"

    async def deliver(
        self,
        payload: DeliveryPayload,
        **kwargs: object,
    ) -> DeliveryResult:
        """Deliver a digest via Slack webhook.

        Args:
            payload: The delivery payload.
            **kwargs: Additional parameters:
                - webhook_url: Override the default webhook URL.

        Returns:
            A DeliveryResult indicating success or failure.
        """
        webhook_url = kwargs.get("webhook_url")
        if webhook_url is not None and isinstance(webhook_url, str):
            url = webhook_url
        else:
            url = self.webhook_url

        try:
            await send_slack(url, payload)
            return DeliveryResult(
                success=True,
                channel=self.channel_name,
            )
        except SlackError as e:
            logger.error(f"Slack delivery failed: {e}")
            return DeliveryResult(
                success=False,
                channel=self.channel_name,
                error_message=str(e),
            )

    async def health_check(self) -> bool:
        """Check if Slack webhook is configured.

        Note: This only checks if the URL is configured, not if it's valid.
        Validating the webhook would require sending a message.
        """
        return bool(self.webhook_url)


# Convenience instance using default settings
slack_delivery = SlackDelivery()
