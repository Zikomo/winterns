"""Authentication routes."""

from fastapi import APIRouter

from wintern.auth.schemas import UserCreate, UserRead, UserUpdate
from wintern.auth.service import (
    fastapi_users,
    google_oauth_client,
    jwt_backend,
)
from wintern.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Register and login routes
router.include_router(
    fastapi_users.get_auth_router(jwt_backend),
    prefix="",
)

# Registration route
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="",
)

# Password reset routes
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="",
)

# Email verification routes
router.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="",
)

# User management routes (me endpoint)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
)

# Google OAuth routes (only if configured)
if settings.google_oauth_client_id and settings.google_oauth_client_secret:
    router.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client,
            jwt_backend,
            settings.secret_key,
            associate_by_email=True,
        ),
        prefix="/google",
    )
