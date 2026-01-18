"""Delivery module - output channels (Slack, email, etc.)."""

from wintern.delivery.base import DeliveryChannel
from wintern.delivery.schemas import DeliveryItem, DeliveryPayload, DeliveryResult
from wintern.delivery.slack import (
    SlackDelivery,
    SlackError,
    SlackRateLimitError,
    SlackWebhookError,
    SlackWebhookMissingError,
    send_slack,
    slack_delivery,
)

__all__ = [
    "DeliveryChannel",
    "DeliveryItem",
    "DeliveryPayload",
    "DeliveryResult",
    "SlackDelivery",
    "SlackError",
    "SlackRateLimitError",
    "SlackWebhookError",
    "SlackWebhookMissingError",
    "send_slack",
    "slack_delivery",
]
