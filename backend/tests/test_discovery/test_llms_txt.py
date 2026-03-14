"""Tests for llms.txt parser."""

from pathlib import Path

import httpx
import pytest

from app.discovery.llms_txt import fetch_llms_txt, parse_llms_txt

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestParseLlmsTxt:
    """Tests for parse_llms_txt()."""

    def test_parses_site_name(self) -> None:
        text = "# MiniMax Platform\n"
        result = parse_llms_txt(text)
        assert result.site_name == "MiniMax Platform"

    def test_parses_site_description(self) -> None:
        text = "# Site\n> A cool site for docs.\n"
        result = parse_llms_txt(text)
        assert result.site_description == "A cool site for docs."

    def test_multiline_description(self) -> None:
        text = "# Site\n> Line one.\n> Line two.\n"
        result = parse_llms_txt(text)
        assert result.site_description == "Line one. Line two."

    def test_parses_sections_and_links(self) -> None:
        result = parse_llms_txt(
            (FIXTURES / "sample_llms.txt").read_text(),
            base_url="https://platform.minimax.io",
        )
        assert result.site_name == "MiniMax Platform"
        assert len(result.pages) == 5

        # Check first page
        assert result.pages[0].title == "Models Introduction"
        assert result.pages[0].url == "https://platform.minimax.io/docs/guides/models-intro"
        assert result.pages[0].section == "Getting Started"
        assert "Overview" in result.pages[0].description

    def test_resolves_relative_urls(self) -> None:
        result = parse_llms_txt(
            (FIXTURES / "sample_llms.txt").read_text(),
            base_url="https://platform.minimax.io",
        )
        quickstart = next(p for p in result.pages if "quickstart" in p.url.lower())
        assert quickstart.url == "https://platform.minimax.io/docs/guides/quickstart"

    def test_preserves_raw_text(self) -> None:
        text = "# Site\n- [Page](https://example.com): Desc\n"
        result = parse_llms_txt(text)
        assert result.raw_text == text

    def test_empty_input(self) -> None:
        result = parse_llms_txt("")
        assert result.pages == []
        assert result.site_name == ""

    def test_no_links(self) -> None:
        result = parse_llms_txt("# Just a heading\n> Description only\n")
        assert result.pages == []
        assert result.site_name == "Just a heading"

    def test_link_without_description(self) -> None:
        text = "- [Page](https://example.com/page)\n"
        result = parse_llms_txt(text)
        assert len(result.pages) == 1
        assert result.pages[0].description == ""

    def test_bare_relative_url(self) -> None:
        text = "- [Page](page/foo)\n"
        result = parse_llms_txt(text, base_url="https://site.com")
        assert result.pages[0].url == "https://site.com/page/foo"

    def test_bare_relative_url_no_base_url_skipped(self) -> None:
        """Bare relative URLs without base_url are skipped (no broken URLs)."""
        text = "- [Page](page/foo)\n"
        result = parse_llms_txt(text, base_url="")
        assert result.pages == []

    def test_absolute_url_different_domain_preserved(self) -> None:
        """Absolute URLs on other domains are kept as-is."""
        text = "- [Other](https://other.com/docs/page): External\n"
        result = parse_llms_txt(text, base_url="https://mysite.com")
        assert result.pages[0].url == "https://other.com/docs/page"


class TestFetchLlmsTxt:
    """Tests for fetch_llms_txt() with mocked HTTP."""

    @pytest.fixture
    def sample_text(self) -> str:
        return (FIXTURES / "sample_llms.txt").read_text()

    async def test_returns_none_on_404(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)
        assert result is None

    async def test_fetches_from_llms_txt_path(self, sample_text: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/llms.txt":
                return httpx.Response(200, text=sample_text)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)

        assert result is not None
        assert result.site_name == "MiniMax Platform"
        assert len(result.pages) == 5

    async def test_falls_back_to_docs_path(self, sample_text: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/docs/llms.txt":
                return httpx.Response(200, text=sample_text)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)

        assert result is not None
        assert len(result.pages) == 5

    async def test_skips_short_responses(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text="short"))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)
        assert result is None

    async def test_handles_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)
        assert result is None

    async def test_rejects_html_error_page(self) -> None:
        """HTML responses are rejected even if status is 200."""
        html = "<html><body>404 Not Found</body></html>" + "x" * 50
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)
        assert result is None

    async def test_falls_back_to_llms_full_txt(self, sample_text: str) -> None:
        """Falls back to /llms-full.txt if other paths fail."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/llms-full.txt":
                return httpx.Response(200, text=sample_text)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_llms_txt("https://example.com", client)

        assert result is not None
        assert len(result.pages) == 5
