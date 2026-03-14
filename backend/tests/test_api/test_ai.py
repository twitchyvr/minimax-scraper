"""Tests for the AI API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.models.db import JobStatus, ScrapeJob


class TestChatEndpoint:
    """Tests for POST /api/ai/chat."""

    async def test_chat_job_not_found(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/ai/chat",
            json={"question": "What is the API?", "job_id": "nonexistent"},
        )
        assert resp.status_code == 404

    async def test_chat_job_no_output(self, client: AsyncClient) -> None:
        import app.storage.database as db_module

        async with db_module.async_session() as session:
            job = ScrapeJob(url="https://example.com", status=JobStatus.COMPLETE)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "What is the API?", "job_id": job_id},
        )
        assert resp.status_code == 400
        assert "no output" in resp.json()["detail"].lower()

    async def test_chat_returns_503_when_not_configured(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        import app.storage.database as db_module

        async with db_module.async_session() as session:
            job = ScrapeJob(
                url="https://example.com",
                status=JobStatus.COMPLETE,
                output_dir=str(tmp_path),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        # Create a markdown file so the index has content
        (tmp_path / "doc.md").write_text("# API Reference\nAPI key setup guide.")

        # Clear cache and client to force fresh initialization
        import app.api.ai as ai_module

        ai_module._index_cache.clear()
        ai_module._llm_client = None

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "API key", "job_id": job_id},
        )
        assert resp.status_code == 503
        assert "MINIMAX_API_KEY" in resp.json()["detail"]

    async def test_chat_success(self, client: AsyncClient, tmp_path: Path) -> None:
        import app.storage.database as db_module

        async with db_module.async_session() as session:
            job = ScrapeJob(
                url="https://example.com",
                status=JobStatus.COMPLETE,
                output_dir=str(tmp_path),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        (tmp_path / "guide.md").write_text("# Setup Guide\nSet your API key in the config file.")

        import app.api.ai as ai_module

        ai_module._index_cache.clear()

        # Mock the LLM client
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(
            return_value=MagicMock(
                content="Set the API key in config [guide.md].",
                model="test-model",
                prompt_tokens=50,
                completion_tokens=10,
            )
        )
        ai_module._llm_client = mock_client

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "API key config", "job_id": job_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "API key" in data["answer"]
        assert "guide.md" in data["sources"]

        # Cleanup
        ai_module._llm_client = None

    async def test_chat_validates_question_length(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/ai/chat",
            json={"question": "", "job_id": "some-id"},
        )
        assert resp.status_code == 422
