"""Tests for the directory structure organizer."""

from app.scraper.organizer import organize_pages


class TestOrganizePages:
    """Tests for organize_pages()."""

    def test_basic_organization(self) -> None:
        pages = [
            {
                "url": "https://example.com/docs/guides/quickstart",
                "title": "Quickstart",
                "section": "",
            },
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert len(result) == 1
        # /docs/ prefix stripped, but guides/ is part of the content hierarchy
        assert result[0].local_path == "guides/quickstart.md"
        assert result[0].title == "Quickstart"

    def test_preserves_directory_structure(self) -> None:
        pages = [
            {
                "url": "https://example.com/docs/api/text/chat",
                "title": "Text Chat",
                "section": "API",
            },
            {
                "url": "https://example.com/docs/api/video/generate",
                "title": "Video Gen",
                "section": "API",
            },
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].local_path == "api/text/chat.md"
        assert result[1].local_path == "api/video/generate.md"

    def test_strips_docs_prefix(self) -> None:
        pages = [
            {"url": "https://example.com/docs/getting-started", "title": "", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].local_path == "getting-started.md"

    def test_strips_base_path(self) -> None:
        pages = [
            {"url": "https://example.com/v2/docs/guides/intro", "title": "", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com/v2/docs")
        assert result[0].local_path == "intro.md"

    def test_handles_md_extension(self) -> None:
        pages = [
            {"url": "https://example.com/docs/page.md", "title": "Page", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].local_path == "page.md"
        assert ".md.md" not in result[0].local_path

    def test_handles_html_extension(self) -> None:
        pages = [
            {"url": "https://example.com/docs/page.html", "title": "Page", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].local_path == "page.md"

    def test_empty_pages(self) -> None:
        assert organize_pages([]) == []

    def test_sanitizes_special_characters(self) -> None:
        pages = [
            {"url": "https://example.com/docs/C++%20Guide", "title": "", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        # ++ becomes -- then collapsed to single -
        assert result[0].local_path == "c-guide.md"

    def test_generates_title_from_path(self) -> None:
        pages = [
            {"url": "https://example.com/docs/getting-started", "title": "", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].title == "Getting Started"

    def test_preserves_section(self) -> None:
        pages = [
            {"url": "https://example.com/docs/page", "title": "Page", "section": "API Reference"},
        ]
        result = organize_pages(pages, base_url="https://example.com")
        assert result[0].section == "API Reference"

    def test_root_path_becomes_index(self) -> None:
        pages = [
            {"url": "https://example.com/docs/", "title": "Docs Home", "section": ""},
        ]
        result = organize_pages(pages, base_url="https://example.com/docs")
        assert result[0].local_path == "index.md"
