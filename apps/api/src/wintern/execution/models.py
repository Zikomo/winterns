"""Execution models - run history and content deduplication."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wintern.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from wintern.winterns.models import Wintern


class RunStatus(str, enum.Enum):
    """Status of a wintern run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WinternRun(TimestampMixin, Base):
    """Record of a single wintern execution."""

    __tablename__ = "wintern_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wintern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("winterns.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), nullable=False, default=RunStatus.PENDING
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Store the generated digest and metadata
    digest_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )  # Source counts, etc.

    # Relationships
    wintern: Mapped[Wintern] = relationship(back_populates="runs")
    seen_contents: Mapped[list[SeenContent]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_wintern_runs_wintern_id_started_at", "wintern_id", "started_at"),)


class SeenContent(Base):
    """Track content that has been processed to avoid duplicates."""

    __tablename__ = "seen_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wintern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("winterns.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wintern_runs.id", ondelete="CASCADE"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 hash of content URL/ID
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    seen_at: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    run: Mapped[WinternRun] = relationship(back_populates="seen_contents")

    __table_args__ = (
        UniqueConstraint("wintern_id", "content_hash", name="uq_seen_content_wintern_hash"),
        Index("ix_seen_content_wintern_id_content_hash", "wintern_id", "content_hash"),
    )
