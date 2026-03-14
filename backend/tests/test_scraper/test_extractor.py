"""Tests for the HTML to markdown extractor."""

from pathlib import Path

from app.scraper.extractor import extract_content

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestExtractContent:
    """Tests for extract_content()."""

    def test_extracts_title_from_h1(self) -> None:
        html = "<html><body><article><h1>My Title</h1><p>Content</p></article></body></html>"
        result = extract_content(html)
        assert result.title == "My Title"

    def test_extracts_title_from_title_tag(self) -> None:
        html = (
            "<html><head><title>Page Title | Docs</title></head>"
            "<body><p>Content here</p></body></html>"
        )
        result = extract_content(html)
        assert result.title == "Page Title"

    def test_title_fallback_to_url(self) -> None:
        html = "<html><body><p>No title in this page at all</p></body></html>"
        result = extract_content(html, url="https://example.com/docs/my-page")
        assert result.title == "My Page"

    def test_removes_navigation(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "Home > Guides" not in result.markdown  # breadcrumb removed
        assert result.title == "Models Introduction"

    def test_removes_footer(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "2025 MiniMax" not in result.markdown

    def test_preserves_code_blocks_with_language(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "```python" in result.markdown
        assert "from openai import OpenAI" in result.markdown

    def test_converts_tables(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "MiniMax-M1" in result.markdown
        assert "General chat" in result.markdown

    def test_handles_warning_callout(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "**Warning**" in result.markdown
        assert "API key" in result.markdown

    def test_handles_note_callout(self) -> None:
        html = (FIXTURES / "sample_doc_page.html").read_text()
        result = extract_content(html)
        assert "**Note**" in result.markdown
        assert "streaming" in result.markdown

    def test_word_count(self) -> None:
        html = (
            "<html><body><article><h1>Title</h1>"
            "<p>One two three four five.</p></article></body></html>"
        )
        result = extract_content(html)
        assert result.word_count > 0

    def test_empty_html(self) -> None:
        result = extract_content("")
        assert result.markdown.strip() == ""

    def test_no_excessive_blank_lines(self) -> None:
        html = "<html><body><p>A</p><br><br><br><br><p>B</p></body></html>"
        result = extract_content(html)
        assert "\n\n\n" not in result.markdown

    def test_code_block_without_language(self) -> None:
        html = "<html><body><article><pre><code>plain code</code></pre></article></body></html>"
        result = extract_content(html)
        assert "```\nplain code\n```" in result.markdown

    def test_url_stored_in_result(self) -> None:
        html = "<html><body><p>Hello</p></body></html>"
        result = extract_content(html, url="https://example.com/page")
        assert result.url == "https://example.com/page"
