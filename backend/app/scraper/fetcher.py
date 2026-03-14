"""Async HTTP fetcher with rate limiting, concurrency control, and retry."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

if TYPE_CHECKING:
    import collections.abc

_ALLOWED_SCHEMES = {"http", "https"}


@dataclass
class FetchResult:
    """Result of fetching a single URL."""

    url: str
    html: str = ""
    status_code: int = 0
    error: str | None = None
    fetch_time_ms: int = 0


class TokenBucket:
    """Token bucket rate limiter.

    Allows bursts up to `capacity` but sustains at most `rate` requests/second.
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock: asyncio.Lock | None = None

    async def acquire(self) -> None:
        """Wait until a token is available."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self._last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Wait for the next token
                wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait)


class Fetcher:
    """Async HTTP fetcher with rate limiting and retries.

    Args:
        rate_limit: Maximum requests per second.
        max_concurrent: Maximum concurrent requests.
        max_retries: Maximum retry attempts for failed requests.
        user_agent: User-Agent header string.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        rate_limit: float = 5.0,
        max_concurrent: int = 5,
        max_retries: int = 3,
        user_agent: str = "minimax-scraper/0.2.1",
        timeout: float = 30.0,
    ) -> None:
        self.rate_limiter = TokenBucket(rate=rate_limit)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL with rate limiting, concurrency control, and retries."""
        # Validate URL scheme to prevent SSRF (file://, ftp://, internal IPs via redirect)
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return FetchResult(url=url, error=f"Disallowed URL scheme: {parsed.scheme}")

        last_status = 0
        async with self.semaphore:
            for attempt in range(self.max_retries + 1):
                await self.rate_limiter.acquire()
                start = time.monotonic()
                try:
                    response = await self.client.get(url)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    last_status = response.status_code

                    if response.status_code == 429:
                        # Rate limited — back off and retry
                        try:
                            retry_after = max(0.0, float(response.headers.get("retry-after", "5")))
                        except (ValueError, OverflowError):
                            retry_after = 5.0
                        if attempt < self.max_retries:
                            await asyncio.sleep(min(retry_after, 30.0))
                            continue
                        # Last attempt — return the 429 as a result
                        return FetchResult(
                            url=url,
                            html="",
                            status_code=429,
                            fetch_time_ms=elapsed_ms,
                        )

                    if response.status_code >= 500 and attempt < self.max_retries:
                        # Server error — exponential backoff
                        await asyncio.sleep(2**attempt)
                        continue

                    return FetchResult(
                        url=url,
                        html=response.text if response.status_code == 200 else "",
                        status_code=response.status_code,
                        fetch_time_ms=elapsed_ms,
                    )
                except httpx.HTTPError as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    if attempt < self.max_retries:
                        await asyncio.sleep(2**attempt)
                        continue
                    return FetchResult(
                        url=url,
                        error=str(e),
                        fetch_time_ms=elapsed_ms,
                    )

        # Exhausted all retries (e.g. persistent 5xx)
        return FetchResult(url=url, status_code=last_status, error="Max retries exceeded")

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """Fetch multiple URLs concurrently with rate limiting."""
        tasks = [self.fetch(url) for url in urls]
        return list(await asyncio.gather(*tasks))

    async def fetch_stream(self, urls: list[str]) -> collections.abc.AsyncIterator[FetchResult]:
        """Fetch URLs concurrently, yielding results as each completes.

        Unlike fetch_many (which blocks until ALL fetches finish), this
        yields each FetchResult as soon as its individual fetch completes.
        This enables real-time progress reporting.
        """
        tasks = {asyncio.ensure_future(self.fetch(url)): url for url in urls}
        for coro in asyncio.as_completed(list(tasks.keys())):
            yield await coro

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
