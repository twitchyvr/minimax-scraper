"""Scrape engine orchestrator.

Coordinates the full pipeline: discover → fetch → extract → organize → write.
"""

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.discovery.engine import DiscoveryResult
from app.scraper.extractor import extract_content
from app.scraper.fetcher import Fetcher
from app.scraper.organizer import OrganizedPage, organize_pages


@dataclass
class ScrapeProgress:
    """Progress update for a scrape job."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    current_url: str = ""


@dataclass
class ScrapedPage:
    """A fully scraped and processed page."""

    url: str
    title: str
    local_path: str
    markdown: str
    word_count: int
    content_hash: str
    fetch_time_ms: int
    section: str = ""
    error: str | None = None


@dataclass
class ScrapeResult:
    """Result of a complete scrape operation."""

    pages: list[ScrapedPage] = field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    discovery_method: str = "none"


async def scrape(
    discovery: DiscoveryResult,
    output_dir: Path,
    fetcher: Fetcher | None = None,
    progress_callback: Callable[["ScrapeProgress"], Awaitable[None]] | None = None,
) -> ScrapeResult:
    """Run the full scrape pipeline.

    Args:
        discovery: Discovery result with pages to scrape.
        output_dir: Directory to write markdown files.
        fetcher: Optional fetcher instance (creates one if not provided).
        progress_callback: Optional async callable(ScrapeProgress) for progress updates.

    Returns:
        ScrapeResult with all scraped pages and statistics.
    """
    if not discovery.pages:
        return ScrapeResult(discovery_method=discovery.method)

    own_fetcher = fetcher is None
    effective_fetcher = fetcher or Fetcher()

    result = ScrapeResult(
        total=len(discovery.pages),
        discovery_method=discovery.method,
    )

    # Organize pages into directory structure
    page_dicts = [{"url": p.url, "title": p.title, "section": p.section} for p in discovery.pages]
    base_url = _extract_base_url(discovery.pages[0].url)
    organized = organize_pages(page_dicts, base_url=base_url)

    # Build URL→organized mapping
    url_to_org: dict[str, OrganizedPage] = {o.url: o for o in organized}

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    progress = ScrapeProgress(total=len(discovery.pages))

    try:
        # Fetch all pages concurrently (rate-limited by fetcher)
        urls = [p.url for p in discovery.pages]
        fetch_results = await effective_fetcher.fetch_many(urls)

        for fetch_result in fetch_results:
            org = url_to_org.get(fetch_result.url)
            local_path = org.local_path if org else "unknown.md"
            section = org.section if org else ""

            if fetch_result.error or not fetch_result.html:
                result.failed += 1
                result.pages.append(
                    ScrapedPage(
                        url=fetch_result.url,
                        title="",
                        local_path=local_path,
                        markdown="",
                        word_count=0,
                        content_hash="",
                        fetch_time_ms=fetch_result.fetch_time_ms,
                        section=section,
                        error=fetch_result.error or f"HTTP {fetch_result.status_code}",
                    )
                )
            else:
                # Extract markdown
                extracted = extract_content(fetch_result.html, url=fetch_result.url)
                content_hash = hashlib.sha256(extracted.markdown.encode()).hexdigest()[:16]

                # Write to disk (with path traversal protection)
                file_path = (output_dir / local_path).resolve()
                if not file_path.is_relative_to(output_dir.resolve()):
                    result.failed += 1
                    result.pages.append(
                        ScrapedPage(
                            url=fetch_result.url,
                            title=extracted.title,
                            local_path=local_path,
                            markdown="",
                            word_count=0,
                            content_hash="",
                            fetch_time_ms=fetch_result.fetch_time_ms,
                            section=section,
                            error="Path traversal rejected",
                        )
                    )
                    continue
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(extracted.markdown, encoding="utf-8")

                result.succeeded += 1
                result.pages.append(
                    ScrapedPage(
                        url=fetch_result.url,
                        title=extracted.title,
                        local_path=local_path,
                        markdown=extracted.markdown,
                        word_count=extracted.word_count,
                        content_hash=content_hash,
                        fetch_time_ms=fetch_result.fetch_time_ms,
                        section=section,
                    )
                )

            # Update progress
            progress.completed = result.succeeded + result.failed
            progress.current_url = fetch_result.url
            if progress_callback is not None:
                await progress_callback(progress)

    finally:
        if own_fetcher:
            await effective_fetcher.close()

    return result


def _extract_base_url(url: str) -> str:
    """Extract the base URL (scheme + host) from a full URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
