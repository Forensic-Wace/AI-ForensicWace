# Contributing to Forensic Wace

Thanks for your interest in contributing! This project started as academic research
and is evolving into a production-grade open-source platform — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for where we are heading. Help is
welcome at every level: code, docs, testing, and WhatsApp schema descriptors.

## Getting started

1. Fork and clone the repository.
2. Backend — create a virtual environment (Python **3.10+** required):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -e "libs/forensicwace_core[postgres]" -e services/api
   cp .env.example .env       # configure FW_* variables — never commit .env
   uvicorn forensicwace_api.main:app --reload --port 8080
   ```
3. Frontend (Node 20+):
   ```bash
   cd frontend && npm install && npm run dev
   ```
4. Or run the whole stack with Docker: see the [README](README.md#quick-start-docker).

## Golden rules

- **Never commit evidence data.** WhatsApp databases, backups, media, or anything
  extracted from a real device must not enter the repository — not even "anonymized"
  samples. The `.gitignore` blocks the common paths and file names, but the
  responsibility is yours. Test fixtures must be fully synthetic.
- **Never commit secrets.** CI runs secret scanning (gitleaks) on every push; a leaked
  key must be rotated, not just removed.
- Evidence databases are opened **read-only**. Any change that could write to an
  evidence file will be rejected.

## Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`.
2. Make your changes. Run linter and tests locally before pushing:
   ```bash
   pip install ruff pytest httpx
   ruff check libs/ services/
   pytest libs/forensicwace_core/tests services/api/tests
   ```
3. Open a Pull Request against `main` using the PR template.

## Adding support for a new WhatsApp schema version

This is one of the most valuable contributions. The plan (see
[docs/ARCHITECTURE.md §4](docs/ARCHITECTURE.md)) moves all WhatsApp SQL into
versioned query packs. Until that lands, open a
[schema support issue](.github/ISSUE_TEMPLATE/schema_support.md) including the table
and column inventory of the unsupported database (**structure only — never row data**).

## Adding a new AI analyzer

1. Create an adapter module in `libs/forensicwace_core/forensicwace_core/analysis/analyzers/`
   exposing `analyze(text) -> list[Finding]` (or a media-enrichment function)
   and `check_status() -> AnalyzerStatus`. Keep heavy imports lazy.
2. Register it in `analysis/analyzers/__init__.py` (`TEXT_ANALYZERS` / `STATUS_CHECKS`).
3. Add its settings to `forensicwace_core/config.py` and document them in `.env.example`.
4. Expose it in the frontend: add the key to `TEXT_ANALYZERS`/`MEDIA_ANALYZERS`
   in `frontend/src/pages/AnalyzePage.tsx`.

## Questions

Open a GitHub Discussion or an issue — there are no bad questions.
