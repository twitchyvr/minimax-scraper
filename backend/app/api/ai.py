"""REST API endpoints for AI features."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from app.ai.chat import CorpusIndex, ask

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.client import LLMAPIError, LLMClient, LLMNotConfiguredError
from app.models.db import JobStatus, ScrapeJob
from app.models.schemas import ChatRequest, ChatResponse
from app.storage.database import get_session

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Maximum number of corpus indexes to keep in memory.
# Each index holds all chunks, IDF tables, and term frequencies for a scraped
# site, so unbounded caching could consume significant memory.
_MAX_INDEX_CACHE_SIZE = 10

# LRU cache: OrderedDict maintains insertion/access order — most recently
# used entries are moved to the end, oldest entries are evicted from the front.
_index_cache: OrderedDict[str, CorpusIndex] = OrderedDict()

# Shared LLM client (reused across requests for connection pooling)
_llm_client: LLMClient | None = None


def _get_llm_client() -> LLMClient:
    """Get or create the shared LLM client."""
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _get_corpus_index(output_dir: str) -> CorpusIndex:
    """Get or build a corpus index, with LRU eviction.

    On cache hit, moves the entry to the end (most recently used).
    On cache miss, builds the index and evicts the oldest entry if at capacity.
    """
    if output_dir in _index_cache:
        _index_cache.move_to_end(output_dir)
        return _index_cache[output_dir]

    index = CorpusIndex.build(Path(output_dir))
    _index_cache[output_dir] = index

    while len(_index_cache) > _MAX_INDEX_CACHE_SIZE:
        _index_cache.popitem(last=False)

    return index


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Ask a question about scraped documentation.

    Uses BM25 search to find relevant context, then sends it to MiniMax M2.5
    for an AI-generated answer with source citations.
    """
    job = await session.get(ScrapeJob, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.output_dir:
        raise HTTPException(status_code=400, detail="Job has no output directory")

    if job.status != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not complete (status: {job.status}). Wait for scraping to finish.",
        )

    index = _get_corpus_index(job.output_dir)
    client = _get_llm_client()

    try:
        result = await ask(
            question=body.question,
            index=index,
            client=client,
            top_k=body.top_k,
        )
    except LLMNotConfiguredError:
        raise HTTPException(
            status_code=503,
            detail="AI features are not configured. Set MINIMAX_API_KEY.",
        ) from None
    except LLMAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI service error: {e}",
        ) from None

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
