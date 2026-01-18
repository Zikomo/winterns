"""Base classes for delivery channel integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wintern.delivery.schemas import DeliveryPayload, DeliveryResult


class DeliveryChannel(ABC):
    """Abstract base class for delivery channel integrations.

    All delivery channels (Slack, email, etc.) should inherit from this
    class and implement the deliver method.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the name identifier for this delivery channel.

        This is used to identify the channel type in logs and results.
        """
        ...

    @abstractmethod
    async def deliver(
        self,
        payload: DeliveryPayload,
        **kwargs: object,
    ) -> DeliveryResult:
        """Deliver a digest via this channel.

        Args:
            payload: The delivery payload containing subject, body, and items.
            **kwargs: Channel-specific parameters.

        Returns:
            A DeliveryResult indicating success or failure.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the delivery channel is available and configured.

        Returns:
            True if the channel is available, False otherwise.
        """
        return True
