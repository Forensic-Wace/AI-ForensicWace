# Contributing to Forensic Wace

Thanks for your interest in contributing! This project started as academic research
and is evolving into a production-grade open-source platform — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for where we are heading. Help is
welcome at every level: code, docs, testing, and WhatsApp schema descriptors.

## Getting started

1. Fork and clone the repository.
2. Create a virtual environment (Python **3.10+** required):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy the configuration template and fill in what you need:
   ```bash
   cp config.ini.example config.ini
   ```
   `config.ini` is gitignored on purpose: the Settings page writes your real API
   keys into it at runtime. **Never commit it.**
4. Set up PostgreSQL as described in the [README](README.md#-installation).

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
2. Make your changes. Run the linter locally before pushing:
   ```bash
   pip install ruff
   ruff check src/
   ```
3. Open a Pull Request against `main` using the PR template.

## Adding support for a new WhatsApp schema version

This is one of the most valuable contributions. The plan (see
[docs/ARCHITECTURE.md §4](docs/ARCHITECTURE.md)) moves all WhatsApp SQL into
versioned query packs. Until that lands, open a
[schema support issue](.github/ISSUE_TEMPLATE/schema_support.md) including the table
and column inventory of the unsupported database (**structure only — never row data**).

## Adding a new AI analyzer

1. Create the service module in `src/forensicWace_SE/services/`.
2. Implement a `check_status()` health check and the main analysis function.
3. Register it in `textServices.py` and add its configuration to `config.ini.example`.
4. Add a UI toggle in the Settings template.

## Questions

Open a GitHub Discussion or an issue — there are no bad questions.
