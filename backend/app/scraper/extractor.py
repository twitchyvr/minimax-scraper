"""HTML to markdown extractor for documentation pages."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter


@dataclass
class ExtractedPage:
    """Result of extracting markdown from an HTML page."""

    url: str
    title: str
    markdown: str
    word_count: int


class DocMarkdownConverter(MarkdownConverter):
    """Custom markdown converter for documentation sites.

    Handles doc-specific elements like callouts/admonitions, tabs,
    and code blocks with language annotations.
    """

    def convert_pre(self, el: Tag, text: str, **kwargs: object) -> str:
        """Handle code blocks — preserve language from class attribute."""
        code_el = el.find("code")
        lang = ""
        if code_el and isinstance(code_el, Tag) and code_el.get("class"):
            code_classes: list[str] = code_el.get("class") or []  # type: ignore[assignment]
            for cls in code_classes:
                if cls.startswith("language-") or cls.startswith("lang-"):
                    lang = cls.split("-", 1)[1]
                    break
                if cls.startswith("hljs"):
                    continue
                # Some sites just use the language name as a class
                if cls in _COMMON_LANGUAGES:
                    lang = cls
                    break

        # Get the raw code text
        code_text = code_el.get_text() if code_el else el.get_text()
        code_text = code_text.strip("\n")
        return f"\n\n```{lang}\n{code_text}\n```\n\n"

    def convert_blockquote(self, el: Tag, text: str, **kwargs: object) -> str:
        """Handle blockquotes and callout/admonition variants."""
        # Check for callout/admonition classes
        bq_classes: list[str] = el.get("class") or []  # type: ignore[assignment]
        if isinstance(bq_classes, list):
            for cls in bq_classes:
                cls_lower = cls.lower()
                if any(kw in cls_lower for kw in ("warning", "danger", "caution", "error")):
                    return f"\n\n> **Warning**\n{_indent_blockquote(text)}\n\n"
                if any(kw in cls_lower for kw in ("note", "info", "tip")):
                    return f"\n\n> **Note**\n{_indent_blockquote(text)}\n\n"

        return f"\n\n{_indent_blockquote(text)}\n\n"

    def convert_table(self, el: Tag, text: str, **kwargs: object) -> str:
        """Let markdownify handle tables but ensure spacing."""
        result: str = super().convert_table(el, text, **kwargs)  # type: ignore[misc]
        return f"\n\n{result}\n\n"


def _indent_blockquote(text: str) -> str:
    """Ensure each line of blockquote text starts with '> '."""
    lines = text.strip().splitlines()
    return "\n".join(f"> {line}" if not line.startswith(">") else line for line in lines)


_COMMON_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "bash",
    "shell",
    "sh",
    "zsh",
    "json",
    "yaml",
    "yml",
    "toml",
    "xml",
    "html",
    "css",
    "sql",
    "graphql",
    "markdown",
    "md",
    "dockerfile",
    "makefile",
    "lua",
    "r",
    "scala",
    "dart",
    "elixir",
    "haskell",
    "perl",
    "powershell",
    "terraform",
    "hcl",
    "protobuf",
    "plaintext",
    "text",
    "curl",
    "http",
}


# Selectors for main content areas across common doc platforms
_CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".markdown-body",
    ".docs-content",
    ".content-body",
    "#content",
    ".page-content",
    ".article-content",
    ".documentation",
]

# Elements to remove before extraction
_REMOVE_SELECTORS = [
    "nav",
    "header",
    "footer",
    ".sidebar",
    ".table-of-contents",
    ".toc",
    ".breadcrumb",
    ".pagination",
    ".edit-page",
    ".feedback",
    "script",
    "style",
    "noscript",
    ".cookie-banner",
    ".announcement-bar",
]


def extract_content(html: str, url: str = "") -> ExtractedPage:
    """Extract markdown content from an HTML documentation page.

    Args:
        html: Raw HTML content.
        url: Source URL (used for title fallback).

    Returns:
        ExtractedPage with title and markdown content.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements BEFORE title extraction so nav/header <h1>s are excluded
    for selector in _REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Extract title (after noise removal to avoid picking up nav/header h1s)
    title = _extract_title(soup)

    # Find main content area
    content = _find_content(soup)

    # Convert to markdown
    converter = DocMarkdownConverter(
        heading_style="atx",
        bullets="-",
        strong_em_symbol="*",
        strip=["img"],
    )
    markdown: str = converter.convert(str(content))

    # Post-process markdown
    markdown = _clean_markdown(markdown)

    word_count = len(markdown.split())

    return ExtractedPage(
        url=url,
        title=title or _title_from_url(url),
        markdown=markdown,
        word_count=word_count,
    )


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract the page title from HTML."""
    # Try h1 first
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    # Fall back to <title>
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        # Strip common suffixes like " | Docs" or " - Documentation"
        for sep in [" | ", " - ", " — ", " · "]:
            if sep in text:
                return text.split(sep)[0].strip()
        return text

    return ""


def _find_content(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    """Find the main content element using common selectors."""
    for selector in _CONTENT_SELECTORS:
        content = soup.select_one(selector)
        if content and len(content.get_text(strip=True)) > 100:
            return content

    # Fallback to body
    body = soup.find("body")
    if body and isinstance(body, Tag):
        return body

    return soup


def _title_from_url(url: str) -> str:
    """Generate a title from a URL path."""
    if not url:
        return ""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    slug = path.split("/")[-1]
    # Remove .md or .html extension
    slug = re.sub(r"\.(md|html?)$", "", slug)
    return slug.replace("-", " ").replace("_", " ").title()


def _clean_markdown(text: str) -> str:
    """Post-process markdown to clean up artifacts."""
    # Unescape backslash-escaped asterisks that form valid bold/italic patterns.
    # markdownify over-escapes * inside table cells, producing \*\*text\*\* instead
    # of **text**.  We restore \*\* pairs first (bold), then lone \* pairs (italic).
    text = re.sub(r"\\\*\\\*(.+?)\\\*\\\*", r"**\1**", text)
    text = re.sub(r"\\\*(.+?)\\\*", r"*\1*", text)

    # Remove trailing whitespace on each line (must run before blank line collapse)
    text = "\n".join(line.rstrip() for line in text.splitlines())

    # Collapse excessive blank lines (more than 2 → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure single trailing newline
    text = text.strip() + "\n"

    return text
