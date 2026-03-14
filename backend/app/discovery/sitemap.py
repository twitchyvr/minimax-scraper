"""Parser for sitemap.xml documentation indexes."""

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from defusedxml import ElementTree

# Cap to prevent memory issues with massive sitemaps
_MAX_URLS = 10_000


@dataclass
class SitemapUrl:
    """A URL discovered from sitemap.xml."""

    url: str
    lastmod: str | None = None


@dataclass
class SitemapResult:
    """Parsed result from sitemap.xml."""

    urls: list[SitemapUrl] = field(default_factory=list)
    is_index: bool = False


def parse_sitemap_xml(xml_text: str, path_filter: str = "/docs") -> SitemapResult:
    """Parse sitemap.xml content, filtering to documentation paths.

    Args:
        xml_text: Raw XML content.
        path_filter: Only include URLs whose path starts with this prefix.
                     Empty string means include all.

    Returns:
        SitemapResult with discovered URLs.
    """
    result = SitemapResult()

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return result

    # Handle namespace (sitemaps use xmlns)
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    # Check if this is a sitemap index (contains other sitemaps)
    sitemap_tags = root.findall(f"{ns}sitemap")
    if sitemap_tags:
        result.is_index = True
        for sitemap in sitemap_tags:
            loc = sitemap.find(f"{ns}loc")
            if loc is not None and loc.text:
                result.urls.append(SitemapUrl(url=loc.text.strip()))
        return result

    # Regular sitemap — extract URLs
    for url_elem in root.findall(f"{ns}url"):
        if len(result.urls) >= _MAX_URLS:
            break

        loc = url_elem.find(f"{ns}loc")
        lastmod = url_elem.find(f"{ns}lastmod")

        if loc is not None and loc.text:
            url = loc.text.strip()
            parsed = urlparse(url)

            # Apply path filter (segment-aware: /docs matches /docs/foo but not /redocs)
            if path_filter and not (
                parsed.path == path_filter
                or parsed.path.startswith(path_filter + "/")
                or parsed.path.startswith(path_filter + "?")
            ):
                continue

            result.urls.append(
                SitemapUrl(
                    url=url,
                    lastmod=lastmod.text.strip() if lastmod is not None and lastmod.text else None,
                )
            )

    return result


async def fetch_sitemap(
    base_url: str,
    client: httpx.AsyncClient,
    path_filter: str = "/docs",
    _depth: int = 0,
) -> SitemapResult | None:
    """Fetch and parse sitemap.xml from a site.

    Handles sitemap indexes by recursively fetching sub-sitemaps (max 2 levels).

    Returns:
        Parsed result, or None if not found.
    """
    if _depth > 2:
        return None

    base = base_url.rstrip("/")
    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/docs/sitemap.xml",
    ]

    for url in candidates:
        try:
            response = await client.get(url, follow_redirects=True)
            content_type = response.headers.get("content-type", "")
            is_xml = "xml" in content_type or response.text.lstrip().startswith("<?xml")

            if response.status_code == 200 and is_xml:
                parsed = parse_sitemap_xml(response.text, path_filter=path_filter)

                # If this is a sitemap index, recursively fetch sub-sitemaps
                if parsed.is_index:
                    merged = SitemapResult()
                    for sub_sitemap in parsed.urls:
                        try:
                            sub_response = await client.get(sub_sitemap.url, follow_redirects=True)
                            sub_ct = sub_response.headers.get("content-type", "")
                            sub_is_xml = "xml" in sub_ct or sub_response.text.lstrip().startswith(
                                "<?xml"
                            )
                            if sub_response.status_code == 200 and sub_is_xml:
                                sub_parsed = parse_sitemap_xml(
                                    sub_response.text, path_filter=path_filter
                                )
                                merged.urls.extend(sub_parsed.urls)
                                if len(merged.urls) >= _MAX_URLS:
                                    merged.urls = merged.urls[:_MAX_URLS]
                                    break
                        except httpx.HTTPError:
                            continue
                    return merged if merged.urls else None

                return parsed if parsed.urls else None
        except httpx.HTTPError:
            continue

    return None
