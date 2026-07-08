# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Report privately via GitHub's ["Report a vulnerability"](../../security/advisories/new)
(Security tab → Advisories). You will receive an acknowledgement within 7 days.

Please include: affected component/version, reproduction steps, and impact assessment.

## Scope notes for a forensic tool

Forensic Wace processes highly sensitive personal data (chat content, PII, media).
The following are treated as security issues, not just bugs:

- Anything that could **modify an evidence database** (evidence must stay read-only).
- Leakage of message content or PII into logs, temp files, or error pages.
- SQL injection, path traversal, or template injection in any user-facing input.
- Weaknesses in the report signing / RFC 3161 timestamping chain.

## Deployment expectations

The current Server Edition is designed for **trusted lab networks**. Do not expose it
directly to the internet: authentication is not yet enforced (multi-user auth is on the
roadmap — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)). Operators are responsible
for network isolation and at-rest encryption of the results database.
