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

The platform enforces **multi-user authentication** (local accounts, argon2id
passwords, JWT session cookie) with two roles: `analyst` and `admin` (user
management and analyzer-registry changes are admin-only). Operators must:

- set a strong `FW_JWT_SECRET` (>= 32 chars) and override the bootstrap
  `FW_ADMIN_PASSWORD` — the compose/Helm defaults are lab-grade placeholders;
- serve over TLS outside a trusted lab (Helm: `ingress.tls` + cert-manager)
  and set `FW_COOKIE_SECURE=true` — the API logs a startup warning otherwise;
- never set `FW_AUTH_DISABLED=true` outside local single-user development;
- remain responsible for network isolation and at-rest encryption of the
  results database (it contains PII by design).

With authentication enabled, the interactive API docs (`/docs`) and the
OpenAPI schema (`/openapi.json`) also require a session: the API surface is
not advertised to anonymous clients.

Prometheus `/metrics` and the health probes are unauthenticated by design:
keep them cluster-internal.
