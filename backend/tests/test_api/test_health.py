"""Tests for the health check endpoint."""

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """Health check returns 200 with version info."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
