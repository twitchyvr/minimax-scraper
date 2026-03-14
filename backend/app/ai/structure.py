"""AI-powered directory structure suggestions using MiniMax M2.5."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.ai.client import LLMClient, LLMError, LLMMessage
from app.scraper.organizer import OrganizedPage, organize_pages

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a documentation structure expert. Given a list of documentation pages \
(each with a URL, title, and optional section), suggest an optimal directory \
hierarchy that groups related pages logically.

Rules:
- Output ONLY valid JSON — no markdown fences, no commentary.
- The JSON must be an array of objects, each with "url" and "path" keys.
- Paths should use forward slashes, end in .md, and be lowercase kebab-case.
- Group related topics into subdirectories (e.g., api-reference/, guides/, etc.).
- Keep directory depth reasonable (max 3 levels).
- Every input URL must appear exactly once in the output.
- Do not invent URLs — only use the ones provided.
"""


def _build_page_list(pages: list[dict[str, str]]) -> str:
    """Format pages for the LLM prompt."""
    lines: list[str] = []
    for i, page in enumerate(pages, 1):
        url = page.get("url", "")
        title = page.get("title", "")
        section = page.get("section", "")
        parts = [f"{i}. URL: {url}"]
        if title:
            parts.append(f"   Title: {title}")
        if section:
            parts.append(f"   Section: {section}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def _parse_response(content: str, pages: list[dict[str, str]]) -> dict[str, str]:
    """Parse LLM response into a URL→path mapping.

    Returns an empty dict if the response is invalid or incomplete.
    """
    # Strip markdown fences if the LLM wraps in ```json
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        data: Any = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("AI structure response is not valid JSON")
        return {}

    if not isinstance(data, list):
        logger.warning("AI structure response is not a JSON array")
        return {}

    input_urls = {p.get("url", "") for p in pages}
    mapping: dict[str, str] = {}

    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        path = item.get("path", "")
        if url in input_urls and isinstance(path, str) and path:
            # Ensure path ends with .md
            if not path.endswith(".md"):
                path = path + ".md"
            # Normalize separators
            path = path.strip("/")
            mapping[url] = path

    # Validate completeness — all input URLs must be covered
    if len(mapping) != len(input_urls):
        logger.warning(
            "AI structure response missing URLs: expected %d, got %d",
            len(input_urls),
            len(mapping),
        )
        return {}

    return mapping


async def suggest_structure(
    pages: list[dict[str, str]],
    *,
    client: LLMClient | None = None,
) -> list[OrganizedPage]:
    """Use AI to suggest an optimal directory structure for discovered pages.

    Falls back to the heuristic organizer if the AI is unavailable or returns
    an invalid response.

    Args:
        pages: List of dicts with 'url', 'title', and optionally 'section'.
        client: Optional LLM client (creates one if not provided).

    Returns:
        List of OrganizedPage with AI-suggested or heuristic local_path assignments.
    """
    if not pages:
        return []

    if client is None:
        client = LLMClient()

    page_list = _build_page_list(pages)
    messages = [
        LLMMessage(role="system", content=_SYSTEM_PROMPT),
        LLMMessage(
            role="user",
            content=f"Organize these {len(pages)} documentation pages into a "
            f"logical directory structure:\n\n{page_list}",
        ),
    ]

    try:
        response = await client.complete(messages, temperature=0.3)
    except LLMError:
        logger.info("AI structure suggestion unavailable, using heuristic fallback")
        return organize_pages(pages)

    mapping = _parse_response(response.content, pages)
    if not mapping:
        logger.info("AI structure response invalid, using heuristic fallback")
        return organize_pages(pages)

    return [
        OrganizedPage(
            url=page.get("url", ""),
            title=page.get("title", ""),
            local_path=mapping[page["url"]],
            section=page.get("section", ""),
        )
        for page in pages
    ]
