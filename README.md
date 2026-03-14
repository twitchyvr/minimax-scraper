# minimax-scraper

A markdown documentation scraper with an OS-like browser UI. Scrapes developer documentation websites into organized markdown directories with intelligent structure detection.

## Features

- **Smart Discovery** — Auto-detects `llms.txt`, `sitemap.xml`, or crawls sidebar navigation to find all doc pages
- **Intelligent Organization** — Analyzes doc structure and creates directory hierarchies matching the logical data flow
- **Clean Markdown** — Converts HTML docs to clean markdown, preserving code blocks, tables, and structure
- **OS-Like Browser UI** — Desktop-style interface with file explorer, terminal, markdown preview, and AI chat panels
- **AI Intelligence** — Uses MiniMax M2.5 to suggest directory structures and answer questions about scraped docs
- **Real-Time Progress** — WebSocket-powered live updates during scraping

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ / FastAPI |
| Frontend | Rust / Dioxus → WASM |
| Storage | Filesystem + SQLite |
| AI | MiniMax M2.5 (OpenAI-compatible) |

## Current Status

The backend scraping engine is under active development:

- [x] **Backend scaffold** — FastAPI, SQLAlchemy async models, Pydantic schemas, config
- [x] **Discovery engine** — llms.txt parser, sitemap.xml parser (with recursive index resolution), engine orchestrator
- [x] **Scrape engine** — Async fetcher (rate limiting, retries, SSRF protection), HTML→markdown extractor, directory organizer, path traversal protection
- [x] **REST API + WebSocket** — Job CRUD, file tree/content browsing, real-time progress via WebSocket
- [x] **Frontend scaffold** — Dioxus WASM desktop layout, scraper panel, terminal, API client, dark OS theme
- [x] **WebSocket integration** — Real-time job progress via WS hook with auto-reconnect, task cancellation, cancel button
- [x] **File explorer** — Recursive tree view with expand/collapse, click-to-open, word count metadata
- [x] **Markdown preview** — pulldown-cmark rendering with ammonia XSS sanitization, 512KB cap
- [x] **AI client + RAG chat** — LLM client wrapper, BM25 search, RAG Q&A with source citations
- [x] **AI REST API** — `POST /api/ai/chat` endpoint with corpus caching and graceful 503 on missing key
- [x] **AI structure suggestions** — MiniMax M2.5 for directory structure optimization with heuristic fallback
- [x] **Frontend AI chat panel** — Chat window with message bubbles, source citations, and loading states

**Tested live**: Discovery engine found **156 pages** on `platform.minimax.io` via llms.txt. Scrape engine successfully fetched and converted 3 pages to clean markdown with correct directory structure. All API endpoints verified via E2E tests. Frontend compiles to WASM with full panel suite (clippy clean, zero warnings). AI chat and structure suggestions tested with mocked LLM — 151 tests passing.

## Quick Start

> **Note:** Backend and frontend are feature-complete for v0.2.0. All panels operational including AI chat.

### Prerequisites

- Python 3.12+
- Rust toolchain with `wasm32-unknown-unknown` target (for frontend, coming later)

### Development

```bash
# Clone the repository
git clone https://github.com/twitchyvr/minimax-scraper.git
cd minimax-scraper

# Backend setup
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests (151 passing)
pytest

# Type check
mypy --strict app/

# Lint
ruff check app/ tests/
```

## Architecture

The system consists of three main components:

1. **Python Backend** — FastAPI server handling scraping, content extraction, and AI-assisted organization
2. **Rust/Dioxus Frontend** — WASM-compiled OS-like desktop interface running in the browser
3. **WebSocket Bridge** — Real-time communication between backend scrape progress and frontend UI

### Scraping Pipeline

```
URL Input → Discovery (llms.txt/sitemap/sidebar) → Fetch → Extract → Organize → Write Markdown
```

## Target Sites

Designed for modern developer documentation platforms:
- Mintlify
- GitBook
- ReadMe
- Docusaurus
- Any site with `llms.txt` or `sitemap.xml`

## License

MIT — see [LICENSE](LICENSE) for details.
