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

## Quick Start

> **Note:** The project is under active development. Setup instructions will be updated as components are built.

### Prerequisites

- Python 3.12+
- Rust toolchain with `wasm32-unknown-unknown` target
- Docker Desktop (for dev container)

### Development

```bash
# Clone the repository
git clone https://github.com/twitchyvr/minimax-scraper.git
cd minimax-scraper

# Start development environment
make dev
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
