"""Tests for execution factories - source and delivery channel creation."""

import uuid

import pytest

from wintern.delivery.base import DeliveryChannel
from wintern.delivery.slack import SlackDelivery
from wintern.execution.factories import (
    UnsupportedDeliveryError,
    UnsupportedSourceError,
    create_data_source,
    create_delivery_channel,
)
from wintern.sources.base import DataSource
from wintern.sources.brave import BraveSearchSource
from wintern.sources.reddit import RedditSource
from wintern.winterns.models import DeliveryConfig, DeliveryType, SourceConfig, SourceType


class TestCreateDataSource:
    """Tests for create_data_source factory function."""

    def test_create_brave_search_source(self):
        """Should create BraveSearchSource for BRAVE_SEARCH type."""
        config = SourceConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            source_type=SourceType.BRAVE_SEARCH,
            config={},
            is_active=True,
        )

        source = create_data_source(config)

        assert isinstance(source, DataSource)
        assert isinstance(source, BraveSearchSource)
        assert source.source_name == "brave_search"

    def test_create_reddit_source(self):
        """Should create RedditSource for REDDIT type."""
        config = SourceConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            source_type=SourceType.REDDIT,
            config={"subreddits": ["python"]},
            is_active=True,
        )

        source = create_data_source(config)

        assert isinstance(source, DataSource)
        assert isinstance(source, RedditSource)
        assert source.source_name == "reddit"

    def test_create_rss_source_unsupported(self):
        """Should raise UnsupportedSourceError for RSS type."""
        config = SourceConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            source_type=SourceType.RSS,
            config={},
            is_active=True,
        )

        with pytest.raises(UnsupportedSourceError) as exc_info:
            create_data_source(config)

        assert exc_info.value.source_type == SourceType.RSS
        assert "rss" in str(exc_info.value).lower()

    def test_create_news_api_source_unsupported(self):
        """Should raise UnsupportedSourceError for NEWS_API type."""
        config = SourceConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            source_type=SourceType.NEWS_API,
            config={},
            is_active=True,
        )

        with pytest.raises(UnsupportedSourceError) as exc_info:
            create_data_source(config)

        assert exc_info.value.source_type == SourceType.NEWS_API
        assert "news_api" in str(exc_info.value).lower()


class TestCreateDeliveryChannel:
    """Tests for create_delivery_channel factory function."""

    def test_create_slack_delivery(self):
        """Should create SlackDelivery for SLACK type."""
        config = DeliveryConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            delivery_type=DeliveryType.SLACK,
            config={},
            is_active=True,
        )

        channel = create_delivery_channel(config)

        assert isinstance(channel, DeliveryChannel)
        assert isinstance(channel, SlackDelivery)
        assert channel.channel_name == "slack"

    def test_create_slack_delivery_with_webhook(self):
        """Should create SlackDelivery with custom webhook URL."""
        webhook_url = "https://hooks.slack.com/services/custom"
        config = DeliveryConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            delivery_type=DeliveryType.SLACK,
            config={"webhook_url": webhook_url},
            is_active=True,
        )

        channel = create_delivery_channel(config)

        assert isinstance(channel, SlackDelivery)
        assert channel._webhook_url == webhook_url

    def test_create_email_delivery_unsupported(self):
        """Should raise UnsupportedDeliveryError for EMAIL type."""
        config = DeliveryConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            delivery_type=DeliveryType.EMAIL,
            config={"to": "user@example.com"},
            is_active=True,
        )

        with pytest.raises(UnsupportedDeliveryError) as exc_info:
            create_delivery_channel(config)

        assert exc_info.value.delivery_type == DeliveryType.EMAIL
        assert "email" in str(exc_info.value).lower()

    def test_create_sms_delivery_unsupported(self):
        """Should raise UnsupportedDeliveryError for SMS type."""
        config = DeliveryConfig(
            id=uuid.uuid4(),
            wintern_id=uuid.uuid4(),
            delivery_type=DeliveryType.SMS,
            config={"phone": "+1234567890"},
            is_active=True,
        )

        with pytest.raises(UnsupportedDeliveryError) as exc_info:
            create_delivery_channel(config)

        assert exc_info.value.delivery_type == DeliveryType.SMS
        assert "sms" in str(exc_info.value).lower()


class TestExceptionMessages:
    """Tests for exception message formatting."""

    def test_unsupported_source_error_message(self):
        """UnsupportedSourceError should have informative message."""
        error = UnsupportedSourceError(SourceType.RSS)

        assert str(error) == "Unsupported source type: rss"
        assert error.source_type == SourceType.RSS

    def test_unsupported_delivery_error_message(self):
        """UnsupportedDeliveryError should have informative message."""
        error = UnsupportedDeliveryError(DeliveryType.EMAIL)

        assert str(error) == "Unsupported delivery type: email"
        assert error.delivery_type == DeliveryType.EMAIL
