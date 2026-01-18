"""Base classes for data source integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wintern.sources.schemas import SearchResult


class DataSource(ABC):
    """Abstract base class for data source integrations.

    All data sources (Brave Search, Reddit, etc.) should inherit from this
    class and implement the search method.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name identifier for this data source.

        This is used to tag search results with their origin.
        """
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        count: int = 10,
        **kwargs: object,
    ) -> list[SearchResult]:
        """Search this data source for the given query.

        Args:
            query: The search query string.
            count: Maximum number of results to return.
            **kwargs: Source-specific parameters.

        Returns:
            A list of SearchResult objects.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the data source is available and configured.

        Returns:
            True if the source is available, False otherwise.
        """
        return True
