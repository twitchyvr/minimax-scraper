"""Discovery engine orchestrator.

Tries discovery strategies in priority order:
1. llms.txt (most structured)
2. sitemap.xml (URL list, less metadata)
3. Sidebar crawl (last resort, fragile)
"""

from dataclasses import dataclass, field

import httpx

from app.discovery.llms_txt import DiscoveredPage, fetch_llms_txt
from app.discovery.sitemap import fetch_sitemap


@dataclass
class DiscoveryResult:
    """Combined result from all discovery strategies."""

    pages: list[DiscoveredPage] = field(default_factory=list)
    method: str = "none"
    raw_llms_txt: str | None = None


async def discover(
    base_url: str,
    client: httpx.AsyncClient | None = None,
    path_filter: str = "/docs",
) -> DiscoveryResult:
    """Discover all documentation pages on a site.

    Tries strategies in priority order: llms.txt → sitemap → sidebar crawl.
    Returns as soon as one strategy succeeds.

    Args:
        base_url: Base URL of the documentation site.
        client: Optional httpx client (creates one if not provided).
        path_filter: Path filter for sitemap URLs.

    Returns:
        DiscoveryResult with discovered pages and method used.
    """
    own_client = client is None
    effective_client = (
        client
        if client is not None
        else httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "minimax-scraper/0.2.1 (documentation archiver)"},
        )
    )

    result = DiscoveryResult()

    try:
        # Strategy 1: llms.txt
        llms_result = await fetch_llms_txt(base_url, effective_client)
        if llms_result and llms_result.pages:
            result.pages = llms_result.pages
            result.method = "llms_txt"
            result.raw_llms_txt = llms_result.raw_text
            return result

        # Strategy 2: sitemap.xml
        sitemap_result = await fetch_sitemap(base_url, effective_client, path_filter=path_filter)
        if sitemap_result and sitemap_result.urls:
            result.pages = [
                DiscoveredPage(url=u.url, title="", section="") for u in sitemap_result.urls
            ]
            result.method = "sitemap"
            return result

        # Strategy 3: Sidebar crawl (TODO — implement in sidebar.py)
        # For now, return empty result

    finally:
        if own_client:
            await effective_client.aclose()

    return result
