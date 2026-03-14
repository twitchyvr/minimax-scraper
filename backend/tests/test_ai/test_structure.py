"""Tests for the AI directory structure suggestion module."""

import json
from unittest.mock import AsyncMock, MagicMock

from app.ai.client import LLMClient, LLMNotConfiguredError, LLMResponse
from app.ai.structure import (
    _build_page_list,
    _parse_response,
    suggest_structure,
)

SAMPLE_PAGES = [
    {"url": "https://example.com/docs/intro", "title": "Introduction", "section": "Guides"},
    {"url": "https://example.com/docs/auth", "title": "Authentication", "section": "Guides"},
    {"url": "https://example.com/docs/api/users", "title": "Users API", "section": "API"},
    {"url": "https://example.com/docs/api/posts", "title": "Posts API", "section": "API"},
]


class TestBuildPageList:
    """Tests for _build_page_list()."""

    def test_formats_all_pages(self) -> None:
        result = _build_page_list(SAMPLE_PAGES)
        assert "1. URL: https://example.com/docs/intro" in result
        assert "Title: Introduction" in result
        assert "Section: Guides" in result
        assert "4. URL: https://example.com/docs/api/posts" in result

    def test_handles_missing_fields(self) -> None:
        pages = [{"url": "https://example.com/page"}]
        result = _build_page_list(pages)
        assert "1. URL: https://example.com/page" in result
        assert "Title:" not in result
        assert "Section:" not in result

    def test_empty_pages(self) -> None:
        assert _build_page_list([]) == ""


class TestParseResponse:
    """Tests for _parse_response()."""

    def test_parses_valid_json(self) -> None:
        response = json.dumps(
            [
                {"url": "https://example.com/docs/intro", "path": "guides/intro.md"},
                {"url": "https://example.com/docs/auth", "path": "guides/auth.md"},
            ]
        )
        pages = [
            {"url": "https://example.com/docs/intro"},
            {"url": "https://example.com/docs/auth"},
        ]
        mapping = _parse_response(response, pages)
        assert mapping == {
            "https://example.com/docs/intro": "guides/intro.md",
            "https://example.com/docs/auth": "guides/auth.md",
        }

    def test_strips_markdown_fences(self) -> None:
        response = '```json\n[{"url": "https://a.com/x", "path": "x.md"}]\n```'
        pages = [{"url": "https://a.com/x"}]
        mapping = _parse_response(response, pages)
        assert mapping == {"https://a.com/x": "x.md"}

    def test_adds_md_extension(self) -> None:
        response = json.dumps([{"url": "https://a.com/x", "path": "guides/x"}])
        pages = [{"url": "https://a.com/x"}]
        mapping = _parse_response(response, pages)
        assert mapping["https://a.com/x"] == "guides/x.md"

    def test_returns_empty_on_invalid_json(self) -> None:
        assert _parse_response("not json", [{"url": "https://a.com"}]) == {}

    def test_returns_empty_on_non_array(self) -> None:
        assert _parse_response('{"url": "x"}', [{"url": "x"}]) == {}

    def test_returns_empty_on_missing_urls(self) -> None:
        response = json.dumps([{"url": "https://a.com/x", "path": "x.md"}])
        pages = [
            {"url": "https://a.com/x"},
            {"url": "https://a.com/y"},  # Not in response
        ]
        mapping = _parse_response(response, pages)
        assert mapping == {}

    def test_ignores_unknown_urls(self) -> None:
        response = json.dumps(
            [
                {"url": "https://a.com/x", "path": "x.md"},
                {"url": "https://a.com/unknown", "path": "unknown.md"},
            ]
        )
        pages = [{"url": "https://a.com/x"}]
        mapping = _parse_response(response, pages)
        assert mapping == {"https://a.com/x": "x.md"}

    def test_strips_leading_slashes(self) -> None:
        response = json.dumps([{"url": "https://a.com/x", "path": "/guides/x.md"}])
        pages = [{"url": "https://a.com/x"}]
        mapping = _parse_response(response, pages)
        assert mapping["https://a.com/x"] == "guides/x.md"


class TestSuggestStructure:
    """Tests for suggest_structure()."""

    async def test_returns_empty_for_empty_pages(self) -> None:
        result = await suggest_structure([])
        assert result == []

    async def test_returns_ai_suggested_paths(self) -> None:
        ai_response = json.dumps(
            [
                {"url": "https://example.com/docs/intro", "path": "guides/intro.md"},
                {"url": "https://example.com/docs/auth", "path": "guides/auth.md"},
                {"url": "https://example.com/docs/api/users", "path": "api-reference/users.md"},
                {"url": "https://example.com/docs/api/posts", "path": "api-reference/posts.md"},
            ]
        )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content=ai_response, model="test")
        )

        result = await suggest_structure(SAMPLE_PAGES, client=mock_client)

        assert len(result) == 4
        assert result[0].local_path == "guides/intro.md"
        assert result[0].title == "Introduction"
        assert result[2].local_path == "api-reference/users.md"

    async def test_falls_back_on_llm_error(self) -> None:
        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(side_effect=LLMNotConfiguredError("No key"))

        result = await suggest_structure(SAMPLE_PAGES, client=mock_client)

        # Should return heuristic results (not empty)
        assert len(result) == 4
        # Heuristic organizer uses URL paths
        assert all(r.local_path.endswith(".md") for r in result)

    async def test_falls_back_on_invalid_response(self) -> None:
        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content="I can't do that", model="test")
        )

        result = await suggest_structure(SAMPLE_PAGES, client=mock_client)

        # Should fall back to heuristic
        assert len(result) == 4

    async def test_falls_back_on_incomplete_response(self) -> None:
        # Only 2 of 4 URLs in the response
        partial_response = json.dumps(
            [
                {"url": "https://example.com/docs/intro", "path": "guides/intro.md"},
                {"url": "https://example.com/docs/auth", "path": "guides/auth.md"},
            ]
        )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content=partial_response, model="test")
        )

        result = await suggest_structure(SAMPLE_PAGES, client=mock_client)

        # Should fall back to heuristic
        assert len(result) == 4

    async def test_preserves_section_info(self) -> None:
        ai_response = json.dumps(
            [
                {"url": "https://example.com/docs/intro", "path": "guides/intro.md"},
                {"url": "https://example.com/docs/auth", "path": "guides/auth.md"},
                {"url": "https://example.com/docs/api/users", "path": "api/users.md"},
                {"url": "https://example.com/docs/api/posts", "path": "api/posts.md"},
            ]
        )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content=ai_response, model="test")
        )

        result = await suggest_structure(SAMPLE_PAGES, client=mock_client)

        assert result[0].section == "Guides"
        assert result[2].section == "API"

    async def test_uses_low_temperature(self) -> None:
        ai_response = json.dumps(
            [
                {"url": "https://example.com/docs/intro", "path": "guides/intro.md"},
                {"url": "https://example.com/docs/auth", "path": "guides/auth.md"},
                {"url": "https://example.com/docs/api/users", "path": "api/users.md"},
                {"url": "https://example.com/docs/api/posts", "path": "api/posts.md"},
            ]
        )

        mock_client = MagicMock(spec=LLMClient)
        mock_client.complete = AsyncMock(
            return_value=LLMResponse(content=ai_response, model="test")
        )

        await suggest_structure(SAMPLE_PAGES, client=mock_client)

        # Verify temperature=0.3 was passed (deterministic output)
        call_kwargs = mock_client.complete.call_args[1]
        assert call_kwargs["temperature"] == 0.3
