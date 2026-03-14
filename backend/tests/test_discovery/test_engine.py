"""Tests for discovery engine orchestrator."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.discovery.engine import discover

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestDiscover:
    """Tests for the discover() orchestrator."""

    @pytest.fixture
    def llms_text(self) -> str:
        return (FIXTURES / "sample_llms.txt").read_text()

    @pytest.fixture
    def sitemap_xml(self) -> str:
        return (FIXTURES / "sample_sitemap.xml").read_text()

    async def test_prefers_llms_txt(self, llms_text: str, sitemap_xml: str) -> None:
        """When both llms.txt and sitemap exist, llms.txt wins."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/llms.txt":
                return httpx.Response(200, text=llms_text)
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sitemap_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await discover("https://example.com", client=client)

        assert result.method == "llms_txt"
        assert len(result.pages) == 5
        assert result.raw_llms_txt is not None

    async def test_falls_back_to_sitemap(self, sitemap_xml: str) -> None:
        """When llms.txt is missing, falls back to sitemap."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sitemap_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await discover("https://example.com", client=client)

        assert result.method == "sitemap"
        assert len(result.pages) == 3  # filtered to /docs

    async def test_returns_empty_when_nothing_found(self) -> None:
        """When no discovery method works, returns empty result."""
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await discover("https://example.com", client=client)

        assert result.method == "none"
        assert result.pages == []

    async def test_creates_own_client_if_none(self) -> None:
        """When no client is passed, creates and closes its own."""
        # Mock both strategies to return nothing — avoids real network calls
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        mock_client = httpx.AsyncClient(transport=transport)

        with patch("app.discovery.engine.httpx.AsyncClient", return_value=mock_client):
            result = await discover("https://example.com", client=None)

        assert result.method == "none"
        assert result.pages == []

    async def test_path_filter_passed_to_sitemap(self, sitemap_xml: str) -> None:
        """Custom path_filter is forwarded to sitemap parser."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sitemap_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await discover("https://example.com", client=client, path_filter="/blog")

        assert result.method == "sitemap"
        assert len(result.pages) == 1
        assert "blog" in result.pages[0].url

    async def test_llms_txt_with_no_pages_falls_through(self) -> None:
        """If llms.txt exists but has no links, falls through to sitemap."""
        llms_no_links = "# Site Name\n> Description only\n"
        sitemap_xml = (FIXTURES / "sample_sitemap.xml").read_text()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/llms.txt":
                return httpx.Response(200, text=llms_no_links)
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sitemap_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await discover("https://example.com", client=client)

        assert result.method == "sitemap"
