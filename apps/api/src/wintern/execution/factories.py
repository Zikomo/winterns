"""Factory functions to create data sources and delivery channels from config."""

from __future__ import annotations

from wintern.delivery.base import DeliveryChannel
from wintern.delivery.slack import SlackDelivery
from wintern.sources.base import DataSource
from wintern.sources.brave import BraveSearchSource
from wintern.sources.reddit import RedditSource
from wintern.winterns.models import DeliveryConfig, DeliveryType, SourceConfig, SourceType


class UnsupportedSourceError(Exception):
    """Raised when attempting to create an unsupported source type."""

    def __init__(self, source_type: SourceType) -> None:
        self.source_type = source_type
        super().__init__(f"Unsupported source type: {source_type.value}")


class UnsupportedDeliveryError(Exception):
    """Raised when attempting to create an unsupported delivery type."""

    def __init__(self, delivery_type: DeliveryType) -> None:
        self.delivery_type = delivery_type
        super().__init__(f"Unsupported delivery type: {delivery_type.value}")


def create_data_source(source_config: SourceConfig) -> DataSource:
    """Create a DataSource instance from a SourceConfig.

    Args:
        source_config: The source configuration from the database.

    Returns:
        A configured DataSource instance.

    Raises:
        UnsupportedSourceError: If the source type is not yet implemented.
    """
    match source_config.source_type:
        case SourceType.BRAVE_SEARCH:
            return BraveSearchSource()
        case SourceType.REDDIT:
            return RedditSource()
        case SourceType.RSS | SourceType.NEWS_API:
            raise UnsupportedSourceError(source_config.source_type)
        case _:
            raise UnsupportedSourceError(source_config.source_type)


def create_delivery_channel(delivery_config: DeliveryConfig) -> DeliveryChannel:
    """Create a DeliveryChannel instance from a DeliveryConfig.

    Args:
        delivery_config: The delivery configuration from the database.

    Returns:
        A configured DeliveryChannel instance.

    Raises:
        UnsupportedDeliveryError: If the delivery type is not yet implemented.
    """
    match delivery_config.delivery_type:
        case DeliveryType.SLACK:
            # Get webhook URL from config if provided, otherwise use default
            webhook_url = delivery_config.config.get("webhook_url")
            return SlackDelivery(webhook_url=webhook_url)
        case DeliveryType.EMAIL | DeliveryType.SMS:
            raise UnsupportedDeliveryError(delivery_config.delivery_type)
        case _:
            raise UnsupportedDeliveryError(delivery_config.delivery_type)
