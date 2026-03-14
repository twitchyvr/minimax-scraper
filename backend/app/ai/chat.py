"""AI Q&A chat over scraped documentation corpus."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 — used at runtime in CorpusIndex.build()
from typing import TYPE_CHECKING

from app.ai.client import LLMClient, LLMMessage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Defaults for retrieval
_DEFAULT_TOP_K = 5
_DEFAULT_CHUNK_SIZE = 1500  # chars per chunk (~300 words)
_DEFAULT_CHUNK_OVERLAP = 200  # char overlap between chunks


@dataclass
class SearchResult:
    """A single search result from the corpus."""

    file_path: str
    chunk: str
    score: float


@dataclass
class ChatResponse:
    """Response from the AI chat."""

    answer: str
    sources: list[str]
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class CorpusIndex:
    """In-memory search index over markdown files.

    Uses BM25-style term frequency scoring for keyword search.
    """

    chunks: list[tuple[str, str]] = field(default_factory=list)  # (file_path, text)
    idf: dict[str, float] = field(default_factory=dict)
    chunk_term_freqs: list[dict[str, int]] = field(default_factory=list)
    avg_chunk_len: float = 0.0

    @classmethod
    def build(
        cls,
        output_dir: Path,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
    ) -> CorpusIndex:
        """Build a search index from markdown files in an output directory.

        Args:
            output_dir: Directory containing scraped markdown files.
            chunk_size: Maximum characters per chunk.
            chunk_overlap: Overlap between consecutive chunks.

        Returns:
            CorpusIndex ready for searching.
        """
        index = cls()

        if not output_dir.is_dir():
            return index

        # Read all markdown files and chunk them
        for md_file in sorted(output_dir.rglob("*.md")):
            relative = str(md_file.relative_to(output_dir))
            text = md_file.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                continue

            for chunk in _chunk_text(text, chunk_size, chunk_overlap):
                index.chunks.append((relative, chunk))

        if not index.chunks:
            return index

        # Build IDF and term frequency tables
        doc_count = len(index.chunks)
        doc_freq: dict[str, int] = {}

        for _, chunk_text in index.chunks:
            terms = _tokenize(chunk_text)
            tf: dict[str, int] = {}
            for term in terms:
                tf[term] = tf.get(term, 0) + 1
            index.chunk_term_freqs.append(tf)

            unique_terms = set(terms)
            for term in unique_terms:
                doc_freq[term] = doc_freq.get(term, 0) + 1

        # IDF = log((N - df + 0.5) / (df + 0.5) + 1) (BM25 formula)
        for term, df in doc_freq.items():
            index.idf[term] = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)

        total_len = sum(len(_tokenize(c)) for _, c in index.chunks)
        index.avg_chunk_len = total_len / doc_count if doc_count else 0.0

        return index

    def search(self, query: str, top_k: int = _DEFAULT_TOP_K) -> list[SearchResult]:
        """Search the corpus for chunks relevant to a query.

        Uses BM25 scoring with k1=1.5, b=0.75.

        Args:
            query: Search query string.
            top_k: Number of top results to return.

        Returns:
            List of SearchResult sorted by relevance score.
        """
        if not self.chunks:
            return []

        query_terms = _tokenize(query)
        if not query_terms:
            return []

        k1 = 1.5
        b = 0.75
        scores: list[tuple[int, float]] = []

        for i, tf in enumerate(self.chunk_term_freqs):
            score = 0.0
            chunk_len = sum(tf.values())
            for term in query_terms:
                if term not in tf:
                    continue
                term_tf = tf[term]
                idf = self.idf.get(term, 0.0)
                numerator = term_tf * (k1 + 1)
                denominator = term_tf + k1 * (1 - b + b * chunk_len / self.avg_chunk_len)
                score += idf * numerator / denominator

            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results: list[SearchResult] = []
        for idx, score in scores[:top_k]:
            file_path, chunk = self.chunks[idx]
            results.append(SearchResult(file_path=file_path, chunk=chunk, score=score))

        return results


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at a paragraph boundary
        if end < len(text):
            newline_pos = text.rfind("\n\n", start, end)
            if newline_pos > start + chunk_size // 2:
                end = newline_pos + 2  # include the double newline

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def _tokenize(text: str) -> list[str]:
    """Simple word tokenization: lowercase, split on non-alphanumeric."""
    return re.findall(r"[a-z0-9]+", text.lower())


_SYSTEM_PROMPT = """\
You are a documentation assistant. Answer the user's question based ONLY on the \
provided documentation excerpts. If the answer is not in the provided context, say so.

When referencing information, cite the source file using [filename.md] notation.

Be concise and direct. Use code examples from the documentation when relevant."""


async def ask(
    question: str,
    index: CorpusIndex,
    client: LLMClient | None = None,
    *,
    top_k: int = _DEFAULT_TOP_K,
    history: list[LLMMessage] | None = None,
) -> ChatResponse:
    """Ask a question about the scraped documentation corpus.

    Args:
        question: User's question.
        index: Pre-built corpus search index.
        client: LLM client (creates one if not provided).
        top_k: Number of context chunks to include.
        history: Optional conversation history for multi-turn chat.

    Returns:
        ChatResponse with answer and source citations.
    """
    if not index.chunks:
        return ChatResponse(
            answer="No documentation has been scraped yet. "
            "Please scrape a documentation site first.",
            sources=[],
        )

    # Search for relevant context
    results = index.search(question, top_k=top_k)

    if not results:
        return ChatResponse(
            answer="I couldn't find any relevant information in the "
            "scraped documentation for your question.",
            sources=[],
        )

    # Assemble context
    context_parts: list[str] = []
    source_files: list[str] = []
    for r in results:
        context_parts.append(f"--- [{r.file_path}] ---\n{r.chunk}")
        if r.file_path not in source_files:
            source_files.append(r.file_path)

    context = "\n\n".join(context_parts)

    # Build messages
    messages: list[LLMMessage] = [LLMMessage(role="system", content=_SYSTEM_PROMPT)]

    if history:
        messages.extend(history)

    user_content = f"Documentation context:\n\n{context}\n\nQuestion: {question}"
    messages.append(LLMMessage(role="user", content=user_content))

    # Get LLM response
    own_client = client is None
    effective_client = client or LLMClient()

    try:
        response = await effective_client.complete(messages)
        return ChatResponse(
            answer=response.content,
            sources=source_files,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
    finally:
        if own_client:
            await effective_client.close()


async def ask_stream(
    question: str,
    index: CorpusIndex,
    client: LLMClient | None = None,
    *,
    top_k: int = _DEFAULT_TOP_K,
    history: list[LLMMessage] | None = None,
) -> AsyncIterator[str]:
    """Stream an answer about the scraped documentation corpus.

    Same as ask() but yields content chunks for real-time display.

    Args:
        question: User's question.
        index: Pre-built corpus search index.
        client: LLM client (creates one if not provided).
        top_k: Number of context chunks to include.
        history: Optional conversation history for multi-turn chat.

    Yields:
        Content string chunks as they arrive from the LLM.
    """
    if not index.chunks:
        yield "No documentation has been scraped yet. Please scrape a documentation site first."
        return

    results = index.search(question, top_k=top_k)

    if not results:
        yield (
            "I couldn't find any relevant information in the "
            "scraped documentation for your question."
        )
        return

    context_parts: list[str] = []
    for r in results:
        context_parts.append(f"--- [{r.file_path}] ---\n{r.chunk}")

    context = "\n\n".join(context_parts)

    messages: list[LLMMessage] = [LLMMessage(role="system", content=_SYSTEM_PROMPT)]

    if history:
        messages.extend(history)

    user_content = f"Documentation context:\n\n{context}\n\nQuestion: {question}"
    messages.append(LLMMessage(role="user", content=user_content))

    own_client = client is None
    effective_client = client or LLMClient()

    try:
        async for chunk in effective_client.stream(messages):
            yield chunk
    finally:
        if own_client:
            await effective_client.close()
