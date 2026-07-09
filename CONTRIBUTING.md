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

This is one of the most valuable contributions, and it requires **no service
code changes**. All WhatsApp SQL lives in versioned query packs under
[schemas/whatsapp/](schemas/whatsapp/):

1. Create `schemas/whatsapp/<platform>/<your-descriptor-id>/descriptor.yaml`
   (copy an existing one): detection rules (`required_tables` with their
   columns, `optional_tables`), the query-name → `.sql` file map, and
   capabilities. Give it a higher `priority` than older generations if it
   should win on databases matching both.
2. Write the parameterized `.sql` files next to it (named parameters only —
   never interpolate values).
3. Add a **synthetic** fixture in `schemas/whatsapp/fixtures/<descriptor-id>.sql`
   (schema subset + fake rows — NEVER derived from real evidence) and register
   it in `EXPECTED_MATCHES` in
   `libs/forensicwace_core/tests/test_schema_registry.py`.
4. Run `pytest libs/forensicwace_core/tests/test_schema_registry.py` — the
   compatibility matrix verifies detection and executes every query in your
   pack against your fixture.

If you hit an unsupported database and can't contribute the pack yourself,
open a [schema support issue](.github/ISSUE_TEMPLATE/schema_support.md) — the
API's unknown-schema error (and the backup overview page) already prints the
exact table/column inventory to attach (**structure only — never row data**).

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
