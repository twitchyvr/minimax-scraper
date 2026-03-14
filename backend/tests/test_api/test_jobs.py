"""Tests for the jobs REST API."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


class TestCreateJob:
    """Tests for POST /api/jobs."""

    async def test_creates_job(self, client: AsyncClient) -> None:
        with patch("app.api.jobs._run_job", new_callable=AsyncMock):
            response = await client.post(
                "/api/jobs",
                json={"url": "https://example.com/docs"},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com/docs"
        assert data["status"] == "pending"
        assert data["id"]

    async def test_invalid_url_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/jobs",
            json={"url": "not-a-url"},
        )
        assert response.status_code == 422


class TestListJobs:
    """Tests for GET /api/jobs."""

    async def test_empty_list(self, client: AsyncClient) -> None:
        response = await client.get("/api/jobs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_created_jobs(self, client: AsyncClient) -> None:
        with patch("app.api.jobs._run_job", new_callable=AsyncMock):
            await client.post("/api/jobs", json={"url": "https://a.com/docs"})
            await client.post("/api/jobs", json={"url": "https://b.com/docs"})

        response = await client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetJob:
    """Tests for GET /api/jobs/{id}."""

    async def test_returns_job(self, client: AsyncClient) -> None:
        with patch("app.api.jobs._run_job", new_callable=AsyncMock):
            create_resp = await client.post("/api/jobs", json={"url": "https://example.com/docs"})
        job_id = create_resp.json()["id"]

        response = await client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["id"] == job_id

    async def test_404_for_missing_job(self, client: AsyncClient) -> None:
        response = await client.get("/api/jobs/nonexistent-id")
        assert response.status_code == 404


class TestCancelJob:
    """Tests for DELETE /api/jobs/{id}."""

    async def test_cancels_pending_job(self, client: AsyncClient) -> None:
        with patch("app.api.jobs._run_job", new_callable=AsyncMock):
            create_resp = await client.post("/api/jobs", json={"url": "https://example.com/docs"})
        job_id = create_resp.json()["id"]

        response = await client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 204

        # Verify job is cancelled
        get_resp = await client.get(f"/api/jobs/{job_id}")
        assert get_resp.json()["status"] == "cancelled"

    async def test_404_for_missing_job(self, client: AsyncClient) -> None:
        response = await client.delete("/api/jobs/nonexistent-id")
        assert response.status_code == 404


class TestGetJobPages:
    """Tests for GET /api/jobs/{id}/pages."""

    async def test_empty_pages(self, client: AsyncClient) -> None:
        with patch("app.api.jobs._run_job", new_callable=AsyncMock):
            create_resp = await client.post("/api/jobs", json={"url": "https://example.com/docs"})
        job_id = create_resp.json()["id"]

        response = await client.get(f"/api/jobs/{job_id}/pages")
        assert response.status_code == 200
        assert response.json() == []

    async def test_404_for_missing_job(self, client: AsyncClient) -> None:
        response = await client.get("/api/jobs/nonexistent-id/pages")
        assert response.status_code == 404
