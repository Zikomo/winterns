"""Tests for Wintern CRUD endpoints."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "wintern-test@example.com") -> str:
    """Helper to register and login, returning the access token."""
    await client.post(
        "/auth/register",
        json={"email": email, "password": "testpassword123"},
    )
    login_response = await client.post(
        "/auth/login",
        data={"username": email, "password": "testpassword123"},
    )
    return login_response.json()["access_token"]


@pytest.mark.asyncio
async def test_list_winterns_empty(client: AsyncClient):
    """Test listing Winterns when user has none."""
    token = await get_auth_token(client, "list-empty@example.com")

    response = await client.get(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert data["active_count"] == 0
    assert data["paused_count"] == 0
    assert data["scheduled_count"] == 0


@pytest.mark.asyncio
async def test_create_wintern(client: AsyncClient):
    """Test creating a new Wintern."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "AI News Digest",
            "description": "Daily digest of AI news",
            "context": "I want to stay updated on the latest AI research and industry news",
            "cron_schedule": "0 9 * * *",
            "source_configs": [
                {
                    "source_type": "brave_search",
                    "config": {"query": "artificial intelligence news"},
                }
            ],
            "delivery_configs": [
                {
                    "delivery_type": "email",
                    "config": {"to": "user@example.com"},
                }
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AI News Digest"
    assert data["description"] == "Daily digest of AI news"
    assert data["is_active"] is True
    assert len(data["source_configs"]) == 1
    assert data["source_configs"][0]["source_type"] == "brave_search"
    assert len(data["delivery_configs"]) == 1
    assert data["delivery_configs"][0]["delivery_type"] == "email"


@pytest.mark.asyncio
async def test_create_wintern_minimal(client: AsyncClient):
    """Test creating a Wintern with minimal required fields."""
    token = await get_auth_token(client, "minimal@example.com")

    response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Simple Wintern",
            "context": "Just a simple research agent",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Simple Wintern"
    assert data["source_configs"] == []
    assert data["delivery_configs"] == []


@pytest.mark.asyncio
async def test_get_wintern(client: AsyncClient):
    """Test getting a single Wintern."""
    token = await get_auth_token(client, "get@example.com")

    # Create a wintern first
    create_response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Test Wintern",
            "context": "Test context",
        },
    )
    wintern_id = create_response.json()["id"]

    # Get the wintern
    response = await client.get(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == wintern_id
    assert data["name"] == "Test Wintern"


@pytest.mark.asyncio
async def test_get_wintern_not_found(client: AsyncClient):
    """Test getting a non-existent Wintern returns 404."""
    token = await get_auth_token(client, "notfound@example.com")

    response = await client.get(
        "/api/v1/winterns/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_wintern_other_user(client: AsyncClient):
    """Test that users cannot access other users' Winterns."""
    # Create wintern as user 1
    token1 = await get_auth_token(client, "user1@example.com")
    create_response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "name": "User 1 Wintern",
            "context": "User 1 context",
        },
    )
    wintern_id = create_response.json()["id"]

    # Try to access as user 2
    token2 = await get_auth_token(client, "user2@example.com")
    response = await client.get(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_wintern(client: AsyncClient):
    """Test updating a Wintern."""
    token = await get_auth_token(client, "update@example.com")

    # Create a wintern
    create_response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Original Name",
            "context": "Original context",
        },
    )
    wintern_id = create_response.json()["id"]

    # Update the wintern
    response = await client.put(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Updated Name",
            "description": "New description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "New description"
    assert data["context"] == "Original context"  # Unchanged


@pytest.mark.asyncio
async def test_update_wintern_preserves_next_run_at(client: AsyncClient):
    """Test that updating unrelated fields doesn't affect next_run_at."""
    token = await get_auth_token(client, "update-schedule@example.com")

    # Create a scheduled wintern
    create_response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Scheduled Wintern",
            "context": "Test context",
            "cron_schedule": "0 9 * * *",
        },
    )
    assert create_response.status_code == 201
    wintern_id = create_response.json()["id"]
    original_next_run_at = create_response.json()["next_run_at"]
    assert original_next_run_at is not None

    # Update only name/description - should NOT affect next_run_at
    response = await client.put(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Renamed Wintern",
            "description": "Added description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Renamed Wintern"
    assert data["next_run_at"] == original_next_run_at  # Unchanged


@pytest.mark.asyncio
async def test_delete_wintern(client: AsyncClient):
    """Test soft deleting a Wintern."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a wintern
    create_response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "To Delete",
            "context": "Will be deleted",
        },
    )
    wintern_id = create_response.json()["id"]

    # Delete the wintern
    response = await client.delete(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # Verify it's soft deleted (still accessible but is_active=False)
    get_response = await client.get(
        f"/api/v1/winterns/{wintern_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_list_winterns_pagination(client: AsyncClient):
    """Test listing Winterns with pagination."""
    token = await get_auth_token(client, "pagination@example.com")

    # Create 5 winterns
    for i in range(5):
        await client.post(
            "/api/v1/winterns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"Wintern {i}",
                "context": f"Context {i}",
            },
        )

    # Get first page
    response = await client.get(
        "/api/v1/winterns?skip=0&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["skip"] == 0
    assert data["limit"] == 2

    # Get second page
    response = await client.get(
        "/api/v1/winterns?skip=2&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert len(data["items"]) == 2
    assert data["skip"] == 2


@pytest.mark.asyncio
async def test_list_winterns_aggregate_counts(client: AsyncClient):
    """Test that aggregate counts are returned correctly across all winterns."""
    token = await get_auth_token(client, "counts@example.com")

    # Create 2 active winterns with schedules (will have next_run_at set)
    for i in range(2):
        await client.post(
            "/api/v1/winterns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"Active Scheduled {i}",
                "context": f"Context {i}",
                "cron_schedule": "0 9 * * *",
            },
        )

    # Create 1 active wintern without schedule
    await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Active No Schedule",
            "context": "No schedule context",
        },
    )

    # Create 2 winterns with schedules and pause them (next_run_at should be cleared)
    for i in range(2):
        create_response = await client.post(
            "/api/v1/winterns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"To Pause {i}",
                "context": f"Will be paused {i}",
                "cron_schedule": "0 10 * * *",
            },
        )
        wintern_id = create_response.json()["id"]
        # Pause by setting is_active=False - should clear next_run_at
        await client.put(
            f"/api/v1/winterns/{wintern_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )

    # List winterns with small page size to test counts are across all, not just page
    response = await client.get(
        "/api/v1/winterns?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify pagination returns only 2 items
    assert len(data["items"]) == 2
    assert data["total"] == 5

    # Counts should reflect all 5 winterns
    assert data["active_count"] == 3
    assert data["paused_count"] == 2
    # Only the 2 active scheduled winterns should be counted (paused ones have next_run_at cleared)
    assert data["scheduled_count"] == 2


@pytest.mark.asyncio
async def test_winterns_unauthorized(client: AsyncClient):
    """Test that unauthenticated requests are rejected."""
    response = await client.get("/api/v1/winterns")
    assert response.status_code == 401

    response = await client.post(
        "/api/v1/winterns",
        json={"name": "Test", "context": "Test"},
    )
    assert response.status_code == 401
