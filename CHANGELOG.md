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
