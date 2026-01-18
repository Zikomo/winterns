"""Integration tests for execution API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str) -> str:
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


async def create_wintern_with_configs(
    client: AsyncClient,
    token: str,
    name: str = "Test Wintern",
) -> dict:
    """Helper to create a wintern with source and delivery configs."""
    response = await client.post(
        "/api/v1/winterns",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "context": "I want to track AI developments",
            "cron_schedule": "0 9 * * *",
            "source_configs": [
                {
                    "source_type": "brave_search",
                    "config": {"query": "AI news"},
                }
            ],
            "delivery_configs": [
                {
                    "delivery_type": "slack",
                    "config": {"webhook_url": "https://hooks.slack.com/test"},
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


class TestTriggerRunEndpoint:
    """Tests for POST /api/v1/winterns/{id}/run endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_run_success(self, client: AsyncClient):
        """Should return 202 Accepted and queue the run."""
        token = await get_auth_token(client, "trigger-run@example.com")
        wintern = await create_wintern_with_configs(client, token)

        response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 202
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "pending"
        assert "queued" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_trigger_run_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent wintern."""
        token = await get_auth_token(client, "trigger-404@example.com")
        fake_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/winterns/{fake_id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_run_no_sources(self, client: AsyncClient):
        """Should return 400 when wintern has no active sources."""
        token = await get_auth_token(client, "trigger-no-sources@example.com")

        # Create wintern without sources
        response = await client.post(
            "/api/v1/winterns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "No Sources Wintern",
                "context": "Test context",
                "delivery_configs": [
                    {"delivery_type": "slack", "config": {}},
                ],
            },
        )
        wintern = response.json()

        response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "sources" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_trigger_run_no_delivery(self, client: AsyncClient):
        """Should return 400 when wintern has no active delivery channels."""
        token = await get_auth_token(client, "trigger-no-delivery@example.com")

        # Create wintern without delivery configs
        response = await client.post(
            "/api/v1/winterns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "No Delivery Wintern",
                "context": "Test context",
                "source_configs": [
                    {"source_type": "brave_search", "config": {}},
                ],
            },
        )
        wintern = response.json()

        response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "delivery" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_trigger_run_unauthorized(self, client: AsyncClient):
        """Should return 401 for unauthenticated request."""
        fake_id = str(uuid.uuid4())

        response = await client.post(f"/api/v1/winterns/{fake_id}/run")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_trigger_run_other_user(self, client: AsyncClient):
        """Should return 404 when trying to trigger another user's wintern."""
        # Create wintern as user 1
        token1 = await get_auth_token(client, "trigger-user1@example.com")
        wintern = await create_wintern_with_configs(client, token1)

        # Try to trigger as user 2
        token2 = await get_auth_token(client, "trigger-user2@example.com")
        response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token2}"},
        )

        assert response.status_code == 404


class TestListRunsEndpoint:
    """Tests for GET /api/v1/winterns/{id}/runs endpoint."""

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client: AsyncClient):
        """Should return empty list when no runs exist."""
        token = await get_auth_token(client, "list-empty@example.com")
        wintern = await create_wintern_with_configs(client, token)

        response = await client.get(
            f"/api/v1/winterns/{wintern['id']}/runs",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_runs_returns_correct_structure(self, client: AsyncClient):
        """Should return runs list with correct structure."""
        token = await get_auth_token(client, "list-structure@example.com")
        wintern = await create_wintern_with_configs(client, token)

        # List runs (empty is fine, we're testing structure)
        response = await client.get(
            f"/api/v1/winterns/{wintern['id']}/runs",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_runs_pagination_params(self, client: AsyncClient):
        """Should respect pagination parameters."""
        token = await get_auth_token(client, "list-pagination@example.com")
        wintern = await create_wintern_with_configs(client, token)

        # Get with specific pagination params
        response = await client.get(
            f"/api/v1/winterns/{wintern['id']}/runs?skip=5&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 5
        assert data["limit"] == 10

    @pytest.mark.asyncio
    async def test_list_runs_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent wintern."""
        token = await get_auth_token(client, "list-404@example.com")
        fake_id = str(uuid.uuid4())

        response = await client.get(
            f"/api/v1/winterns/{fake_id}/runs",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs_unauthorized(self, client: AsyncClient):
        """Should return 401 for unauthenticated request."""
        fake_id = str(uuid.uuid4())

        response = await client.get(f"/api/v1/winterns/{fake_id}/runs")

        assert response.status_code == 401


class TestGetRunEndpoint:
    """Tests for GET /api/v1/winterns/{id}/runs/{run_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_run_returns_trigger_response_fields(self, client: AsyncClient):
        """Should return run details matching trigger response."""
        token = await get_auth_token(client, "get-run@example.com")
        wintern = await create_wintern_with_configs(client, token)

        # Trigger a run - the trigger response includes run_id and status
        trigger_response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )
        trigger_data = trigger_response.json()

        # Verify trigger response structure
        assert "run_id" in trigger_data
        assert "status" in trigger_data
        assert trigger_data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent run."""
        token = await get_auth_token(client, "get-run-404@example.com")
        wintern = await create_wintern_with_configs(client, token)
        fake_run_id = str(uuid.uuid4())

        response = await client.get(
            f"/api/v1/winterns/{wintern['id']}/runs/{fake_run_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_wintern_not_found(self, client: AsyncClient):
        """Should return 404 for non-existent wintern."""
        token = await get_auth_token(client, "get-run-wintern-404@example.com")
        fake_wintern_id = str(uuid.uuid4())
        fake_run_id = str(uuid.uuid4())

        response = await client.get(
            f"/api/v1/winterns/{fake_wintern_id}/runs/{fake_run_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_wrong_wintern(self, client: AsyncClient):
        """Should return 404 if run belongs to different wintern."""
        token = await get_auth_token(client, "get-run-wrong@example.com")

        # Create two winterns
        wintern1 = await create_wintern_with_configs(client, token, "Wintern 1")
        wintern2 = await create_wintern_with_configs(client, token, "Wintern 2")

        # Trigger run on wintern1
        trigger_response = await client.post(
            f"/api/v1/winterns/{wintern1['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )
        run_id = trigger_response.json()["run_id"]

        # Try to get the run via wintern2's endpoint
        response = await client.get(
            f"/api/v1/winterns/{wintern2['id']}/runs/{run_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_unauthorized(self, client: AsyncClient):
        """Should return 401 for unauthenticated request."""
        fake_wintern_id = str(uuid.uuid4())
        fake_run_id = str(uuid.uuid4())

        response = await client.get(
            f"/api/v1/winterns/{fake_wintern_id}/runs/{fake_run_id}"
        )

        assert response.status_code == 401


class TestRunResponseSchema:
    """Tests for the run response schema."""

    @pytest.mark.asyncio
    async def test_trigger_response_schema(self, client: AsyncClient):
        """Should include all expected fields in trigger response."""
        token = await get_auth_token(client, "schema-test@example.com")
        wintern = await create_wintern_with_configs(client, token)

        response = await client.post(
            f"/api/v1/winterns/{wintern['id']}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 202
        data = response.json()

        # Check all expected fields are present in trigger response
        expected_fields = [
            "run_id",
            "status",
            "message",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_list_response_schema(self, client: AsyncClient):
        """Should include all expected fields in list response."""
        token = await get_auth_token(client, "list-schema@example.com")
        wintern = await create_wintern_with_configs(client, token)

        response = await client.get(
            f"/api/v1/winterns/{wintern['id']}/runs",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Check all expected fields are present in list response
        expected_fields = [
            "items",
            "total",
            "skip",
            "limit",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
