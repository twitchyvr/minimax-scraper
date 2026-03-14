"""Tests for the browse REST API."""

from pathlib import Path

from httpx import AsyncClient

from app.models.db import JobStatus, ScrapeJob
from tests.conftest import test_session


class TestGetFileTree:
    """Tests for GET /api/browse/{job_id}/tree."""

    async def test_returns_tree(self, client: AsyncClient, tmp_path: Path) -> None:
        # Create a job with output directory
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            job.output_dir = str(tmp_path)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        # Create some files
        (tmp_path / "guides").mkdir()
        (tmp_path / "guides" / "quickstart.md").write_text("# Quick Start\n")
        (tmp_path / "api-reference.md").write_text("# API\n")

        response = await client.get(f"/api/browse/{job_id}/tree")
        assert response.status_code == 200
        data = response.json()

        # Should have directory + file at top level
        names = {n["name"] for n in data}
        assert "guides" in names
        assert "api-reference.md" in names

        # Directory should have children
        guides = next(n for n in data if n["name"] == "guides")
        assert guides["is_dir"] is True
        assert len(guides["children"]) == 1
        assert guides["children"][0]["name"] == "quickstart.md"

    async def test_404_for_missing_job(self, client: AsyncClient) -> None:
        response = await client.get("/api/browse/nonexistent/tree")
        assert response.status_code == 404

    async def test_404_when_no_output_dir(self, client: AsyncClient) -> None:
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.PENDING)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        response = await client.get(f"/api/browse/{job_id}/tree")
        assert response.status_code == 404

    async def test_skips_hidden_files(self, client: AsyncClient, tmp_path: Path) -> None:
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            job.output_dir = str(tmp_path)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        (tmp_path / ".hidden.md").write_text("hidden")
        (tmp_path / "_metadata").mkdir()
        (tmp_path / "visible.md").write_text("visible")

        response = await client.get(f"/api/browse/{job_id}/tree")
        names = {n["name"] for n in response.json()}
        assert "visible.md" in names
        assert ".hidden.md" not in names
        assert "_metadata" not in names


class TestGetFileContent:
    """Tests for GET /api/browse/{job_id}/file."""

    async def test_returns_content(self, client: AsyncClient, tmp_path: Path) -> None:
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            job.output_dir = str(tmp_path)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        (tmp_path / "page.md").write_text("# Hello World\n")

        response = await client.get(f"/api/browse/{job_id}/file", params={"path": "page.md"})
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "# Hello World\n"
        assert data["path"] == "page.md"

    async def test_path_traversal_rejected(self, client: AsyncClient, tmp_path: Path) -> None:
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            job.output_dir = str(tmp_path)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        response = await client.get(
            f"/api/browse/{job_id}/file",
            params={"path": "../../etc/passwd"},
        )
        assert response.status_code == 403

    async def test_404_for_missing_file(self, client: AsyncClient, tmp_path: Path) -> None:
        async with test_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            job.output_dir = str(tmp_path)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        response = await client.get(
            f"/api/browse/{job_id}/file",
            params={"path": "nonexistent.md"},
        )
        assert response.status_code == 404
