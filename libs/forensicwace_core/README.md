# forensicwace-core

Shared core library of the Forensic Wace platform: configuration, evidence
backup discovery, read-only WhatsApp SQLite extraction (parameterized queries),
the AI analysis pipeline and forensic report generation (RFC 3161 timestamped
PDFs).

Consumed by `services/api` (and, from Phase 3, by the queue-driven analysis
workers). Heavy analyzer dependencies are optional extras:

```bash
pip install -e "libs/forensicwace_core[postgres]"            # minimal
pip install -e "libs/forensicwace_core[all]"                 # every analyzer stack
```

Configuration is environment-based (`FW_*` variables) — see `.env.example`
at the repository root and `forensicwace_core/config.py`.
