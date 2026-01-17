"""FastAPI Users configuration and service setup."""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from httpx_oauth.clients.google import GoogleOAuth2
from sqlalchemy.ext.asyncio import AsyncSession

from wintern.auth.models import AccessToken, OAuthAccount, User
from wintern.core.config import settings
from wintern.core.database import async_session

log = structlog.get_logger()


# Google OAuth client
google_oauth_client = GoogleOAuth2(
    client_id=settings.google_oauth_client_id,
    client_secret=settings.google_oauth_client_secret,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    async with async_session() as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def get_user_db(
    session: AsyncSessionDep,
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """Get the user database adapter."""
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


UserDbDep = Annotated[SQLAlchemyUserDatabase, Depends(get_user_db)]


async def get_access_token_db(
    session: AsyncSessionDep,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase, None]:
    """Get the access token database adapter."""
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """User manager with custom logic for user lifecycle events."""

    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request: Request | None = None):
        """Called after a user registers."""
        log.info("User registered", user_id=str(user.id), email=user.email)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        """Called after a user requests a password reset."""
        log.info(
            "Password reset requested",
            user_id=str(user.id),
            email=user.email,
        )

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        """Called after a user requests email verification."""
        log.info(
            "Verification requested",
            user_id=str(user.id),
            email=user.email,
        )


async def get_user_manager(
    user_db: UserDbDep,
) -> AsyncGenerator[UserManager, None]:
    """Get the user manager instance."""
    yield UserManager(user_db)


# JWT Authentication
bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_jwt_strategy() -> JWTStrategy:
    """Get the JWT strategy for authentication."""
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.access_token_expire_minutes * 60,
    )


jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# FastAPIUsers instance
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [jwt_backend],
)
