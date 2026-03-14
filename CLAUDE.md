# minimax-scraper — Claude Code Instructions

## Project Overview

A markdown documentation scraper with an OS-like browser UI. Python/FastAPI backend + Rust/Dioxus WASM frontend.

## Stack

- **Backend:** Python 3.12+ / FastAPI / SQLite / httpx / BeautifulSoup / markdownify
- **Frontend:** Rust / Dioxus → WASM / dioxus-mosaic / pulldown-cmark
- **AI:** MiniMax M2.5 (OpenAI-compatible API)
- **Communication:** WebSocket (real-time) + REST (CRUD)

## 8-Stage Continuous Development Loop — MANDATORY

Every code change — every Issue, every fix, every feature — must pass all 8 stages before advancing. No exceptions. Failures at any stage loop back to Stage 1.

```
┌─→ 1. CODE ──→ 2. ITERATE ──→ 3. STATIC TEST ──→ 4. DEEP STATIC TEST ─┐
│                                                                         │
│   5. CHECK SYNTAX ──→ 6. CODE REVIEW ──→ 7. E2E ──→ 8. DOGFOOD ──────┘
│                                                         │
└─────────────────────────────────────────────────────────┘
```

| Stage | What | Backend | Frontend |
|-------|------|---------|----------|
| 1. Code | Write or modify code | Edit files | Edit files |
| 2. Iterate | Re-read, check edge cases, refine | Read changed files | Read changed files |
| 3. Static Test | Run test suite — zero failures | `cd backend && pytest` | `cd frontend && cargo test` |
| 4. Deep Static Test | Type checking + architecture | `cd backend && mypy --strict app/` | `cd frontend && cargo clippy -- -D warnings` |
| 5. Check Syntax | Lint and formatting | `cd backend && ruff check app/ && ruff format --check app/` | `cd frontend && cargo fmt --check` |
| 6. Code Review | Subagent reviews the diff | Git diff → review agent | Git diff → review agent |
| 7. E2E | Runtime verification | `uvicorn app.main:app` + Playwright | `dx serve` + Playwright |
| 8. Dogfood | Use the feature as a real user | Scrape a real site, verify output | Use every UI panel end-to-end |

**Why this exists:** Too many instances of AI claiming a bug is "fixed" but actually making it worse or breaking something else. No single stage is sufficient. Only the full loop catches everything. This prevents unchecked changes from reaching production.

## Testing Commands

```bash
# Backend
cd backend && pytest                              # Stage 3: Static Test
cd backend && mypy --strict app/                  # Stage 4: Deep Static Test
cd backend && ruff check app/ && ruff format --check app/  # Stage 5: Check Syntax

# Frontend
cd frontend && cargo test                          # Stage 3: Static Test
cd frontend && cargo clippy -- -D warnings         # Stage 4: Deep Static Test
cd frontend && cargo fmt --check                   # Stage 5: Check Syntax

# E2E
npx playwright test                                # Stage 7: E2E

# All at once
make test                                          # Runs all tests
make lint                                          # Runs all linters
```

## Git Workflow

1. Every change traces to a GitHub Issue
2. Feature branches from `develop`: `feat/`, `fix/`, `docs/`, `refactor/`
3. PRs with code review — subagent reviews every PR before merge
4. Individual dogfooding per Issue before closure
5. Conventional Commits: `type(scope): subject`
6. Always include: `Co-Authored-By: Claude <noreply@anthropic.com>`

## After Every Merged Issue/PR — MANDATORY

1. Update `README.md` to reflect current project state
2. Update `CHANGELOG.md` with entry under `[Unreleased]`
3. Update GitHub Wiki if architecture, setup, or workflow changed
4. Proactively file new GitHub Issues for bugs, improvements, and ideas found during dogfooding

## Project Structure

- `backend/` — Python FastAPI server (scraping, AI, API)
- `frontend/` — Rust/Dioxus WASM app (OS-like browser UI)
- `output/` — Default scrape output directory
- `.github/` — Issue templates, PR template, CI/CD workflows

## Key Architectural Decisions

- **Discovery cascade:** llms.txt → sitemap.xml → sidebar crawl (in that priority order)
- **Markdown conversion:** Custom `markdownify.MarkdownConverter` subclass for doc-site-specific elements
- **Window manager:** dioxus-mosaic for tiling panel layout
- **Markdown preview:** pulldown-cmark compiled to WASM (no server round-trip)
- **AI provider:** MiniMax M2.5 via OpenAI-compatible API (dogfooding their own docs)
