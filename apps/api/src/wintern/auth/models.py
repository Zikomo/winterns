"""User and OAuth account models for fastapi-users."""

import uuid

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from wintern.core.database import Base, TimestampMixin


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """OAuth account model for storing OAuth provider connections."""

    __tablename__ = "oauth_accounts"

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:  # type: ignore[override]  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )

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
    def user_id(cls) -> Mapped[uuid.UUID]:  # type: ignore[override]  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
