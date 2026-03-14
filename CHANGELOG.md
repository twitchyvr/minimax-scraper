# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and repository setup
- GitHub issue templates (bug report, feature request, refactor, documentation)
- Pull request template with checklist
- CI/CD workflow for backend and frontend
- Project CLAUDE.md with 8-stage continuous development loop
- README with project overview and architecture
- CONTRIBUTING guide with branch strategy and commit format
- MIT License
- Makefile with unified development commands
- Docker dev container configuration
- Backend scaffold: FastAPI app, SQLAlchemy models, Pydantic schemas, async SQLite (#1)
- Discovery engine with three-strategy cascade: llms.txt → sitemap.xml → sidebar crawl (#2)
- llms.txt parser with section extraction, relative URL resolution, HTML rejection
- sitemap.xml parser with defusedxml, recursive sitemap index resolution, segment-aware path filtering
- Discovery engine orchestrator with automatic client management and strategy fallback
- 41 discovery tests covering parsers, HTTP mocking, edge cases, and live E2E validation
- Scrape engine with full pipeline: discover → fetch → extract → organize → write (#3)
- Async HTTP fetcher with token-bucket rate limiting, semaphore concurrency, exponential backoff retries
- SSRF protection: URL scheme validation (only http/https allowed)
- HTML→markdown extractor with custom MarkdownConverter for code blocks, callouts, tables
- Directory structure organizer with segment-aware sanitization and common prefix stripping
- Scrape engine orchestrator with path traversal protection and typed async progress callback
- 33 scraper tests covering fetcher, extractor, and organizer modules
- E2E validated against live MiniMax docs (3 pages scraped with correct structure)
- REST API: POST/GET/DELETE /api/jobs, GET /api/jobs/{id}/pages for job lifecycle (#4)
- File browsing API: GET /api/browse/{id}/tree (recursive file tree), GET /api/browse/{id}/file (raw markdown)
- WebSocket: WS /api/ws/{job_id} for real-time scrape progress, error, and completion events
- Concurrent job limit (10 max), sanitized WS error messages, file size limit (10 MB)
- 21 API tests covering endpoints, error cases, path traversal, and WebSocket
- Rust/Dioxus WASM frontend scaffold with OS-like desktop layout (#9)
- Desktop workspace with taskbar panel toggles and window chrome (title bar, close)
- Scraper panel: URL input, job creation via REST, job list with progress bars
- Terminal panel: color-coded log viewer (ERROR/WARN/INFO)
- HTTP API client (gloo-net) for all backend endpoints
- Dark OS theme CSS with CSS variables, monospace terminal, custom scrollbars
- Global reactive state via Signal<AppState> context provider
- WebSocket hook (`use_job_websocket`) with auto-reconnect and exponential backoff (#10)
- Task cancellation on job change prevents leaked background tasks
- Log message cap (500 max) with drain to prevent unbounded memory growth
- JobCard component with real-time progress bar, status badge, and cancel button
- Fixed Dioxus.toml: `[web.resource.dev]` section and `[[web.proxy]]` array syntax for Dioxus 0.6
- File explorer panel with recursive tree view, expand/collapse, and click-to-open (#11)
- Markdown preview panel with pulldown-cmark rendering and ammonia XSS sanitization
- 512KB file size cap prevents UI freeze on large markdown files
- URL-encoded file paths in browse API calls for special character safety
- Stale preview content cleared on job switch and new file selection
- Dark theme CSS for explorer tree, markdown headings, code blocks, tables, blockquotes
