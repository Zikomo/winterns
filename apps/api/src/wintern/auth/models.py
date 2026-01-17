"""User and OAuth account models for fastapi-users."""

import uuid

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from wintern.core.database import Base, TimestampMixin


class OAuthAccount(Base):
    """OAuth account model for storing OAuth provider connections."""

    __tablename__ = "oauth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    oauth_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_token: Mapped[str] = mapped_column(String(1024), nullable=False)
    expires_at: Mapped[int | None] = mapped_column(nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    account_id: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Relationship back to user
    user: Mapped["User"] = relationship(back_populates="oauth_accounts")


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    """User model with UUID primary key and OAuth support."""

    __tablename__ = "users"

    # fastapi-users provides: id, email, hashed_password, is_active, is_superuser, is_verified
    # TimestampMixin provides: created_at, updated_at

    # OAuth accounts relationship
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="joined"
    )


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """Access token model for token-based authentication."""

    @declared_attr
    def user_id(self) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
