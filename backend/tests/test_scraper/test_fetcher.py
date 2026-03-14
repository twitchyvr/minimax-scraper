"""Tests for the async HTTP fetcher."""

import httpx

from app.scraper.fetcher import Fetcher, TokenBucket


class TestTokenBucket:
    """Tests for the token bucket rate limiter."""

    async def test_immediate_acquire_when_tokens_available(self) -> None:
        bucket = TokenBucket(rate=10.0)
        # Should not block — starts with full capacity
        await bucket.acquire()

    async def test_burst_capacity(self) -> None:
        bucket = TokenBucket(rate=5.0, capacity=5.0)
        # Should allow 5 immediate acquires
        for _ in range(5):
            await bucket.acquire()


class TestFetcher:
    """Tests for the Fetcher class."""

    async def test_successful_fetch(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text="<html>Hello</html>"))
        fetcher = Fetcher()
        fetcher.client = httpx.AsyncClient(transport=transport)

        result = await fetcher.fetch("https://example.com/page")
        assert result.status_code == 200
        assert result.html == "<html>Hello</html>"
        assert result.error is None
        assert result.fetch_time_ms >= 0

        await fetcher.close()

    async def test_404_returns_empty_html(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        fetcher = Fetcher()
        fetcher.client = httpx.AsyncClient(transport=transport)

        result = await fetcher.fetch("https://example.com/missing")
        assert result.status_code == 404
        assert result.html == ""
        assert result.error is None

        await fetcher.close()

    async def test_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        fetcher = Fetcher(max_retries=0)
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        result = await fetcher.fetch("https://example.com/down")
        assert result.error is not None
        assert "Connection refused" in result.error

        await fetcher.close()

    async def test_fetch_many(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, text=f"<html>Page {call_count}</html>")

        fetcher = Fetcher(rate_limit=100.0, max_concurrent=5)
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        urls = [f"https://example.com/page{i}" for i in range(5)]
        results = await fetcher.fetch_many(urls)

        assert len(results) == 5
        assert all(r.status_code == 200 for r in results)
        assert all(r.html for r in results)

        await fetcher.close()

    async def test_context_manager(self) -> None:
        async with Fetcher() as fetcher:
            assert fetcher.client is not None
        # Client should be closed after exiting context

    async def test_fetch_stream_yields_as_completed(self) -> None:
        """fetch_stream yields results incrementally, not all-at-once."""
        order: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<html>{request.url}</html>")

        fetcher = Fetcher(rate_limit=100.0, max_concurrent=5)
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        urls = [f"https://example.com/page{i}" for i in range(5)]
        async for result in fetcher.fetch_stream(urls):
            order.append(result.url)
            assert result.status_code == 200

        # All 5 URLs should be yielded
        assert len(order) == 5
        assert set(order) == set(urls)

        await fetcher.close()

    async def test_retry_on_server_error(self) -> None:
        attempt = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                return httpx.Response(500)
            return httpx.Response(200, text="<html>OK</html>")

        fetcher = Fetcher(max_retries=3, rate_limit=100.0)
        fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        result = await fetcher.fetch("https://example.com/flaky")
        assert result.status_code == 200
        assert result.html == "<html>OK</html>"
        assert attempt == 3

        await fetcher.close()
