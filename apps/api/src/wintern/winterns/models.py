"""Wintern domain models - agent configuration and scheduling."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wintern.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from wintern.execution.models import WinternRun


class SourceType(str, enum.Enum):
    """Supported data source types."""

    BRAVE_SEARCH = "brave_search"
    REDDIT = "reddit"
    RSS = "rss"
    NEWS_API = "news_api"


class DeliveryType(str, enum.Enum):
    """Supported delivery channel types."""

    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"


class Wintern(TimestampMixin, Base):
    """A configured research agent (wintern) owned by a user."""

    __tablename__ = "winterns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str] = mapped_column(Text, nullable=False)  # User's research context/prompt
    is_active: Mapped[bool] = mapped_column(default=True)
    cron_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Cron expression
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    source_configs: Mapped[list[SourceConfig]] = relationship(
        back_populates="wintern", cascade="all, delete-orphan"
    )
    delivery_configs: Mapped[list[DeliveryConfig]] = relationship(
        back_populates="wintern", cascade="all, delete-orphan"
    )
    runs: Mapped[list[WinternRun]] = relationship(
        "WinternRun", back_populates="wintern", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_winterns_user_id", "user_id"),
        Index("ix_winterns_next_run_at", "next_run_at"),
    )


class SourceConfig(TimestampMixin, Base):
    """Configuration for a data source used by a wintern."""

    __tablename__ = "source_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wintern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("winterns.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )  # Source-specific config (e.g., subreddits, search queries)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    wintern: Mapped[Wintern] = relationship(back_populates="source_configs")


class DeliveryConfig(TimestampMixin, Base):
    """Configuration for a delivery channel used by a wintern."""

    __tablename__ = "delivery_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wintern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("winterns.id", ondelete="CASCADE"), nullable=False
    )
    delivery_type: Mapped[DeliveryType] = mapped_column(Enum(DeliveryType), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )  # Channel-specific config (e.g., webhook URL, email address)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    wintern: Mapped[Wintern] = relationship(back_populates="delivery_configs")
