"""Tests for the AI API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.api.ai import _MAX_INDEX_CACHE_SIZE, _get_corpus_index, _index_cache
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

    async def test_chat_returns_502_on_llm_api_error(
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

        (tmp_path / "doc.md").write_text("# API\nSome content.")

        import app.api.ai as ai_module
        from app.ai.client import LLMAPIError

        ai_module._index_cache.clear()

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(side_effect=LLMAPIError("rate limit exceeded"))
        ai_module._llm_client = mock_client

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "API info", "job_id": job_id},
        )
        assert resp.status_code == 502
        assert "AI service error" in resp.json()["detail"]

        ai_module._llm_client = None

    async def test_chat_rejects_incomplete_job(self, client: AsyncClient, tmp_path: Path) -> None:
        import app.storage.database as db_module

        async with db_module.async_session() as session:
            job = ScrapeJob(
                url="https://example.com",
                status=JobStatus.SCRAPING,
                output_dir=str(tmp_path),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "What is the API?", "job_id": job_id},
        )
        assert resp.status_code == 400
        assert "not complete" in resp.json()["detail"].lower()

    async def test_chat_validates_top_k_bounds(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/ai/chat",
            json={"question": "test", "job_id": "some-id", "top_k": 0},
        )
        assert resp.status_code == 422

        resp = await client.post(
            "/api/ai/chat",
            json={"question": "test", "job_id": "some-id", "top_k": 25},
        )
        assert resp.status_code == 422


class TestCorpusIndexCache:
    """Tests for LRU eviction of corpus index cache."""

    def test_cache_returns_same_index_on_hit(self, tmp_path: Path) -> None:
        """Cache hit should return the same object without rebuilding."""
        _index_cache.clear()
        d = tmp_path / "job-1"
        d.mkdir()
        (d / "doc.md").write_text("# Hello")

        idx1 = _get_corpus_index(str(d))
        idx2 = _get_corpus_index(str(d))
        assert idx1 is idx2

        _index_cache.clear()

    def test_cache_evicts_oldest_entry(self, tmp_path: Path) -> None:
        """When cache exceeds max size, the oldest (least recently used) entry is evicted."""
        _index_cache.clear()

        dirs: list[str] = []
        for i in range(_MAX_INDEX_CACHE_SIZE + 1):
            d = tmp_path / f"job-{i}"
            d.mkdir()
            (d / "doc.md").write_text(f"# Doc {i}")
            dirs.append(str(d))
            _get_corpus_index(str(d))

        # Cache should be at max size, not max + 1
        assert len(_index_cache) == _MAX_INDEX_CACHE_SIZE
        # The first entry (job-0) should have been evicted
        assert dirs[0] not in _index_cache
        # The last entry should still be present
        assert dirs[-1] in _index_cache

        _index_cache.clear()

    def test_cache_hit_refreshes_access_order(self, tmp_path: Path) -> None:
        """Accessing a cached entry should move it to the end (most recent)."""
        _index_cache.clear()

        dirs: list[str] = []
        for i in range(_MAX_INDEX_CACHE_SIZE):
            d = tmp_path / f"job-{i}"
            d.mkdir()
            (d / "doc.md").write_text(f"# Doc {i}")
            dirs.append(str(d))
            _get_corpus_index(str(d))

        # Access the first entry to refresh it
        _get_corpus_index(dirs[0])

        # Now add one more — should evict job-1 (the true oldest), not job-0
        overflow = tmp_path / "job-overflow"
        overflow.mkdir()
        (overflow / "doc.md").write_text("# Overflow")
        _get_corpus_index(str(overflow))

        assert len(_index_cache) == _MAX_INDEX_CACHE_SIZE
        assert dirs[0] in _index_cache  # was refreshed, should survive
        assert dirs[1] not in _index_cache  # true oldest, should be evicted

        _index_cache.clear()
