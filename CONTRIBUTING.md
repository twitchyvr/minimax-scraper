# Contributing to minimax-scraper

## Branch Strategy

| Branch | Purpose | Merges To |
|--------|---------|-----------|
| `main` | Stable, protected — no direct pushes | — |
| `develop` | Integration branch | `main` (via release PR) |
| `feat/*` | New features | `develop` |
| `fix/*` | Bug fixes | `develop` |
| `docs/*` | Documentation only | `develop` |
| `refactor/*` | Code restructuring | `develop` |

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): subject

Body explaining what and why (not how).

Co-Authored-By: Claude <noreply@anthropic.com>
Closes #<issue-number>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`, `build`

## Pull Request Process

1. Create a feature branch from `develop`
2. Make changes, following the 8-stage development loop
3. Open a PR linking to the relevant Issue (`Closes #N`)
4. Ensure all CI checks pass (lint, type-check, tests, build)
5. Get code review approval
6. Merge to `develop`

## Development Setup

### Using Docker (recommended)

```bash
# Open in VS Code, it will prompt "Reopen in Container"
code .
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Frontend:**
```bash
cd frontend
rustup target add wasm32-unknown-unknown
cargo install dioxus-cli
dx serve
```

## Testing

```bash
# Run all tests
make test

# Backend only
make test-backend

# Frontend only
make test-frontend

# Lint
make lint
```

## Code Style

- **Python:** Formatted with `ruff format`, linted with `ruff check`, type-checked with `mypy --strict`
- **Rust:** Formatted with `cargo fmt`, linted with `cargo clippy -- -D warnings`
