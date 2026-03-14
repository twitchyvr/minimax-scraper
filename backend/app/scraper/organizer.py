"""Directory structure organizer for scraped documentation."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class OrganizedPage:
    """A page with its assigned output path."""

    url: str
    title: str
    local_path: str
    section: str = ""


def organize_pages(
    pages: list[dict[str, str]],
    base_url: str = "",
) -> list[OrganizedPage]:
    """Organize pages into a directory structure based on URL paths and section hints.

    Args:
        pages: List of dicts with 'url', 'title', and optionally 'section' keys.
        base_url: Base URL of the documentation site (used to extract relative paths).

    Returns:
        List of OrganizedPage with local_path assignments.
    """
    if not pages:
        return []

    base_parsed = urlparse(base_url) if base_url else None
    base_path = base_parsed.path.rstrip("/") if base_parsed else ""

    organized: list[OrganizedPage] = []

    for page in pages:
        url = page.get("url", "")
        title = page.get("title", "")
        section = page.get("section", "")

        parsed = urlparse(url)
        path = parsed.path

        # Strip the base path prefix to get the relative doc path
        if base_path and path.startswith(base_path):
            path = path[len(base_path) :]

        # Clean up the path
        path = path.strip("/")

        # Remove common prefixes like 'docs/' that are part of the URL but not the content hierarchy
        path = _strip_common_prefixes(path)

        # Remove file extensions
        path = re.sub(r"\.(md|html?)$", "", path)

        if not path:
            path = "index"

        # Convert to filesystem-safe path
        local_path = _to_safe_path(path) + ".md"

        organized.append(
            OrganizedPage(
                url=url,
                title=title or _title_from_path(path),
                local_path=local_path,
                section=section,
            )
        )

    return organized


def _strip_common_prefixes(path: str) -> str:
    """Strip common URL prefixes that don't add value to directory structure."""
    prefixes = ["docs/", "documentation/", "guide/", "guides/", "reference/"]
    for prefix in prefixes:
        if path.startswith(prefix):
            stripped = path[len(prefix) :]
            # Only strip if there's something left
            if stripped:
                return stripped
    return path


def _to_safe_path(path: str) -> str:
    """Convert a URL path to a filesystem-safe path."""
    # Replace URL-unfriendly characters
    path = path.replace("%20", "-")
    # Keep slashes for directory structure, sanitize segments
    segments = path.split("/")
    safe_segments = [_sanitize_segment(s) for s in segments if s]
    return "/".join(safe_segments)


def _sanitize_segment(segment: str) -> str:
    """Make a single path segment filesystem-safe."""
    # Convert to lowercase kebab-case
    segment = segment.lower()
    # Replace non-alphanumeric (except hyphens) with hyphens
    segment = re.sub(r"[^a-z0-9\-]", "-", segment)
    # Collapse multiple hyphens
    segment = re.sub(r"-+", "-", segment)
    # Strip leading/trailing hyphens
    return segment.strip("-")


def _title_from_path(path: str) -> str:
    """Generate a readable title from a path."""
    slug = path.split("/")[-1]
    slug = re.sub(r"\.(md|html?)$", "", slug)
    return slug.replace("-", " ").replace("_", " ").title()
