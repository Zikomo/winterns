"""Authentication dependencies for use in route handlers."""

from wintern.auth.service import fastapi_users

# Dependency to get the current active user
current_user = fastapi_users.current_user(active=True)

# Dependency to get the current active verified user
current_verified_user = fastapi_users.current_user(active=True, verified=True)

# Dependency to get the current superuser
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Optional current user (returns None if not authenticated)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
