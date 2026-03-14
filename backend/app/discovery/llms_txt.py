"""Parser for the llms.txt documentation index format.

The llms.txt standard (https://llmstxt.org/) provides a machine-readable
index of documentation pages. Format:

    # Site Name
    > Site description

    ## Section Name
    - [Page Title](url): Description
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


@dataclass
class DiscoveredPage:
    """A page discovered from llms.txt."""

    url: str
    title: str
    description: str = ""
    section: str = ""


@dataclass
class LlmsTxtResult:
    """Parsed result from an llms.txt file."""

    site_name: str = ""
    site_description: str = ""
    pages: list[DiscoveredPage] = field(default_factory=list)
    raw_text: str = ""


# Matches markdown links with optional description: [title](url): description
_LINK_PATTERN = re.compile(r"-\s*\[([^\]]+)\]\(([^)]+)\)(?:\s*:\s*(.+))?")


def parse_llms_txt(text: str, base_url: str = "") -> LlmsTxtResult:
    """Parse llms.txt content into structured data.

    Args:
        text: Raw llms.txt content.
        base_url: Base URL for resolving relative links.

    Returns:
        LlmsTxtResult with site info and discovered pages.
    """
    result = LlmsTxtResult(raw_text=text)
    current_section = ""

    for line in text.splitlines():
        line = line.strip()

        # H1: Site name
        if line.startswith("# ") and not line.startswith("## "):
            result.site_name = line[2:].strip()
            continue

        # Blockquote: Site description
        if line.startswith("> "):
            desc = line[2:].strip()
            if result.site_description:
                result.site_description += " " + desc
            else:
                result.site_description = desc
            continue

        # H2: Section header
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        # Link: - [title](url): description
        match = _LINK_PATTERN.match(line)
        if match:
            title = match.group(1).strip()
            url = match.group(2).strip()
            description = (match.group(3) or "").strip()

            # Resolve relative URLs
            if url.startswith("/") and base_url:
                url = base_url.rstrip("/") + url
            elif not url.startswith("http") and base_url:
                url = base_url.rstrip("/") + "/" + url
            elif not url.startswith("http"):
                # No base_url and not absolute — skip this broken link
                continue

            result.pages.append(
                DiscoveredPage(
                    url=url,
                    title=title,
                    description=description,
                    section=current_section,
                )
            )

    return result


async def fetch_llms_txt(base_url: str, client: httpx.AsyncClient) -> LlmsTxtResult | None:
    """Fetch and parse llms.txt from a documentation site.

    Tries /llms.txt and /docs/llms.txt.

    Returns:
        Parsed result, or None if not found.
    """
    base = base_url.rstrip("/")
    candidates = [
        f"{base}/llms.txt",
        f"{base}/docs/llms.txt",
        f"{base}/llms-full.txt",
    ]

    for url in candidates:
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200 and len(response.text) > 50:
                # Reject HTML error pages masquerading as llms.txt
                if response.text.lstrip().startswith("<"):
                    continue

                # Extract base URL for resolving relative links
                parsed = urlparse(base)
                site_root = f"{parsed.scheme}://{parsed.netloc}"
                return parse_llms_txt(response.text, base_url=site_root)
        except httpx.HTTPError:
            continue

    return None
