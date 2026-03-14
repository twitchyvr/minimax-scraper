"""Tests for sitemap.xml parser."""

from pathlib import Path

import httpx
import pytest

from app.discovery.sitemap import fetch_sitemap, parse_sitemap_xml

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestParseSitemapXml:
    """Tests for parse_sitemap_xml()."""

    def test_parses_urls_with_docs_filter(self) -> None:
        xml = (FIXTURES / "sample_sitemap.xml").read_text()
        result = parse_sitemap_xml(xml, path_filter="/docs")
        # Should include /docs/* URLs but not /blog/*
        assert len(result.urls) == 3
        urls = [u.url for u in result.urls]
        assert "https://example.com/docs/getting-started" in urls
        assert "https://example.com/docs/api-reference" in urls
        assert "https://example.com/docs/guides/quickstart" in urls
        assert "https://example.com/blog/announcement" not in urls

    def test_parses_lastmod(self) -> None:
        xml = (FIXTURES / "sample_sitemap.xml").read_text()
        result = parse_sitemap_xml(xml, path_filter="/docs")
        getting_started = next(u for u in result.urls if "getting-started" in u.url)
        assert getting_started.lastmod == "2025-01-15"

    def test_lastmod_none_when_missing(self) -> None:
        xml = (FIXTURES / "sample_sitemap.xml").read_text()
        result = parse_sitemap_xml(xml, path_filter="/docs")
        quickstart = next(u for u in result.urls if "quickstart" in u.url)
        assert quickstart.lastmod is None

    def test_no_filter_returns_all(self) -> None:
        xml = (FIXTURES / "sample_sitemap.xml").read_text()
        result = parse_sitemap_xml(xml, path_filter="")
        assert len(result.urls) == 4

    def test_sitemap_index(self) -> None:
        xml = (FIXTURES / "sample_sitemap_index.xml").read_text()
        result = parse_sitemap_xml(xml)
        assert result.is_index is True
        assert len(result.urls) == 2
        urls = [u.url for u in result.urls]
        assert "https://example.com/sitemap-docs.xml" in urls
        assert "https://example.com/sitemap-blog.xml" in urls

    def test_path_filter_segment_aware(self) -> None:
        """Filter /docs should not match /redocs or /api-docs."""
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/docs/page</loc></url>
          <url><loc>https://example.com/redocs/page</loc></url>
          <url><loc>https://example.com/api-docs/page</loc></url>
        </urlset>"""
        result = parse_sitemap_xml(xml, path_filter="/docs")
        assert len(result.urls) == 1
        assert result.urls[0].url == "https://example.com/docs/page"

    def test_invalid_xml(self) -> None:
        result = parse_sitemap_xml("not xml at all")
        assert result.urls == []

    def test_empty_xml(self) -> None:
        result = parse_sitemap_xml('<?xml version="1.0"?><urlset></urlset>')
        assert result.urls == []

    def test_no_namespace(self) -> None:
        xml = """<?xml version="1.0"?>
        <urlset>
          <url><loc>https://example.com/docs/page</loc></url>
        </urlset>"""
        result = parse_sitemap_xml(xml, path_filter="/docs")
        assert len(result.urls) == 1


class TestFetchSitemap:
    """Tests for fetch_sitemap() with mocked HTTP."""

    @pytest.fixture
    def sample_xml(self) -> str:
        return (FIXTURES / "sample_sitemap.xml").read_text()

    async def test_returns_none_on_404(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)
        assert result is None

    async def test_fetches_from_sitemap_xml(self, sample_xml: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sample_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)

        assert result is not None
        assert len(result.urls) == 3  # /docs filter applied

    async def test_falls_back_to_docs_sitemap(self, sample_xml: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/docs/sitemap.xml":
                return httpx.Response(
                    200,
                    text=sample_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)

        assert result is not None

    async def test_skips_non_xml_content_type(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                text="<html>not a sitemap</html>",
                headers={"content-type": "text/html"},
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)
        assert result is None

    async def test_handles_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)
        assert result is None

    async def test_recursive_sitemap_index(self) -> None:
        """Sitemap indexes are fetched recursively to get actual page URLs."""
        index_xml = (FIXTURES / "sample_sitemap_index.xml").read_text()
        page_xml = (FIXTURES / "sample_sitemap.xml").read_text()

        def handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)
            if path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=index_xml,
                    headers={"content-type": "application/xml"},
                )
            if "sitemap-" in path:
                return httpx.Response(
                    200,
                    text=page_xml,
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_sitemap("https://example.com", client)

        assert result is not None
        # Both sub-sitemaps return the same 3 /docs URLs, so we get 6 total
        assert len(result.urls) == 6
        # All should be actual page URLs, not XML file URLs
        for u in result.urls:
            assert not u.url.endswith(".xml")
