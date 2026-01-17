"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration with duplicate email fails."""
    # Register first user
    await client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "testpassword123",
        },
    )

    # Try to register with same email
    response = await client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "anotherpassword",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    """Test user login returns JWT token."""
    # First register a user
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "testpassword123",
        },
    )

    # Login
    response = await client.post(
        "/auth/login",
        data={
            "username": "login@example.com",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials fails."""
    response = await client.post(
        "/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient):
    """Test getting current user with valid token."""
    # Register and login
    await client.post(
        "/auth/register",
        json={
            "email": "me@example.com",
            "password": "testpassword123",
        },
    )
    login_response = await client.post(
        "/auth/login",
        data={
            "username": "me@example.com",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/auth/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(client: AsyncClient):
    """Test getting current user without token fails."""
    response = await client.get("/auth/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint."""
    # Register and login
    await client.post(
        "/auth/register",
        json={
            "email": "logout@example.com",
            "password": "testpassword123",
        },
    )
    login_response = await client.post(
        "/auth/login",
        data={
            "username": "logout@example.com",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Logout
    response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    # JWT logout typically returns 204 or 200
    assert response.status_code in [200, 204]
