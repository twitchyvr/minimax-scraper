"""Tests for the AI chat module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.ai.chat import (
    ChatResponse,
    CorpusIndex,
    _chunk_text,
    _tokenize,
    ask,
)
from app.ai.client import LLMClient, LLMResponse


class TestTokenize:
    """Tests for the tokenizer."""

    def test_basic_tokenization(self) -> None:
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self) -> None:
        assert _tokenize("hello, world!") == ["hello", "world"]

    def test_handles_code_terms(self) -> None:
        tokens = _tokenize("API key: sk_123abc")
        assert "api" in tokens
        assert "sk" in tokens
        assert "123abc" in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


class TestChunkText:
    """Tests for text chunking."""

    def test_short_text_single_chunk(self) -> None:
        chunks = _chunk_text("Short text.", 100, 20)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_splits_long_text(self) -> None:
        text = "word " * 200  # ~1000 chars
        chunks = _chunk_text(text, 100, 20)
        assert len(chunks) > 1

    def test_prefers_paragraph_boundaries(self) -> None:
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = _chunk_text(text, 30, 5)
        # Should try to break at \n\n
        assert any("\n\n" not in c.strip() for c in chunks)

    def test_overlap_between_chunks(self) -> None:
        text = "a" * 300
        chunks = _chunk_text(text, 100, 20)
        assert len(chunks) >= 3


class TestCorpusIndex:
    """Tests for corpus index building and searching."""

    def test_build_from_directory(self, tmp_path: Path) -> None:
        (tmp_path / "guide.md").write_text("# API Guide\nHow to use the REST API.")
        (tmp_path / "ref.md").write_text("# Reference\nEndpoint: POST /api/chat")

        index = CorpusIndex.build(tmp_path)
        assert len(index.chunks) >= 2
        assert index.avg_chunk_len > 0

    def test_build_empty_directory(self, tmp_path: Path) -> None:
        index = CorpusIndex.build(tmp_path)
        assert len(index.chunks) == 0

    def test_build_nonexistent_directory(self) -> None:
        index = CorpusIndex.build(Path("/nonexistent/dir"))
        assert len(index.chunks) == 0

    def test_build_skips_empty_files(self, tmp_path: Path) -> None:
        (tmp_path / "empty.md").write_text("")
        (tmp_path / "content.md").write_text("# Has Content\nSome text here.")

        index = CorpusIndex.build(tmp_path)
        assert len(index.chunks) == 1

    def test_search_returns_relevant_results(self, tmp_path: Path) -> None:
        (tmp_path / "api.md").write_text("# REST API\nThe REST API supports JSON requests.")
        (tmp_path / "audio.md").write_text(
            "# Audio\nText to speech synthesis using neural networks."
        )

        index = CorpusIndex.build(tmp_path)
        results = index.search("REST API JSON")

        assert len(results) > 0
        assert results[0].file_path == "api.md"
        assert results[0].score > 0

    def test_search_empty_index(self) -> None:
        index = CorpusIndex()
        results = index.search("anything")
        assert results == []

    def test_search_empty_query(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("# Doc\nContent here.")
        index = CorpusIndex.build(tmp_path)
        results = index.search("")
        assert results == []

    def test_search_respects_top_k(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"doc{i}.md").write_text(f"# Document {i}\nAPI reference page {i}.")

        index = CorpusIndex.build(tmp_path)
        results = index.search("API reference", top_k=3)
        assert len(results) == 3

    def test_search_ranks_by_relevance(self, tmp_path: Path) -> None:
        (tmp_path / "relevant.md").write_text(
            "# Video API\nvideo generation video model video endpoint video params"
        )
        (tmp_path / "unrelated.md").write_text(
            "# Text API\ntext generation text model text endpoint"
        )

        index = CorpusIndex.build(tmp_path)
        results = index.search("video generation")

        assert len(results) >= 1
        assert results[0].file_path == "relevant.md"


class TestAsk:
    """Tests for the ask() function."""

    async def test_ask_with_empty_corpus(self) -> None:
        index = CorpusIndex()
        result = await ask("What is the API?", index)

        assert isinstance(result, ChatResponse)
        assert "No documentation" in result.answer
        assert result.sources == []

    async def test_ask_with_no_results(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("# Unrelated\nThis is about cooking.")
        index = CorpusIndex.build(tmp_path)
        result = await ask("quantum physics equations", index)

        # Should either find something or say it couldn't
        assert isinstance(result, ChatResponse)

    async def test_ask_calls_llm_with_context(self, tmp_path: Path) -> None:
        (tmp_path / "api.md").write_text(
            "# API Key\nThe API key is required. Set your API key in the config."
        )
        index = CorpusIndex.build(tmp_path)

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(
                content="You need an API key [api.md].",
                model="test-model",
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                finish_reason="stop",
            )
        )
        mock_client.close = AsyncMock()

        result = await ask("API key config", index, client=mock_client)

        assert result.answer == "You need an API key [api.md]."
        assert "api.md" in result.sources
        assert result.model == "test-model"
        assert result.prompt_tokens == 100

        # Verify the LLM was called with context
        call_args = mock_client.complete.call_args[0][0]
        assert any("api.md" in m.content for m in call_args if m.role == "user")

    async def test_ask_includes_history(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text(
            "# Documentation\nDocumentation content about API usage and setup."
        )
        index = CorpusIndex.build(tmp_path)

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content="Follow-up answer.", finish_reason="stop")
        )
        mock_client.close = AsyncMock()

        from app.ai.client import LLMMessage

        history = [
            LLMMessage(role="user", content="First question"),
            LLMMessage(role="assistant", content="First answer"),
        ]

        await ask("documentation API usage", index, client=mock_client, history=history)

        messages = mock_client.complete.call_args[0][0]
        # Should include system + history + user message
        assert len(messages) >= 4
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert messages[1].content == "First question"
