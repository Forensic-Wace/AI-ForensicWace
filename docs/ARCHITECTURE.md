# Forensic Wace — Open Source & Microservices Architecture Plan

> Status: **PROPOSAL — under review**
> Scope: evolution of the current research-grade monolith into an open-source,
> containerized, horizontally scalable platform (Docker Compose first, Kubernetes second).

---

## 1. Goals

1. **Open-source ready**: no secrets or real case data in the repo, CI, contribution workflow.
2. **FE/BE separation**: React SPA talking to a stateless JSON API.
3. **Microservices**: extraction, analysis, and reporting split into independently deployable services.
4. **Async analysis pipeline**: message-queue based workers, the natural unit of autoscaling.
5. **WhatsApp DB schema versioning**: detect the schema version of an evidence DB and pick the right query set automatically.
6. **Two deployment tiers**: `docker compose up` for contributors and small labs; Helm chart + autoscaling (KEDA) for production.

### Non-goals (for now)

- Multi-tenant SaaS features (billing, orgs). Multi-user auth *is* in scope.
- Rewriting the AI analyzers themselves — they stay as the existing external containers (DeepPass, Whisper, Tesseract, LAVIS) plus cloud connectors.

---

## 2. Current State Assessment

| Area | Today | Problem |
|---|---|---|
| App shape | Flask monolith, `main.py` (~1,100 lines) does routing + rendering + orchestration | No independent scaling, hard to test, hard to contribute to |
| Session state | In-memory `hostsData` dict keyed on `request.remote_addr` (`main.py`) | Breaks behind NAT/proxy; impossible to run >1 replica |
| Frontend | Jinja2 + Bootstrap 5 templates rendered server-side | FE and BE cannot evolve or deploy independently |
| WhatsApp queries | Hardcoded SQL strings in `globalConstants.py` (iOS) and `repository/android_query.py` (Android) | No schema-version awareness; breaks silently when WhatsApp changes its schema |
| Query construction | String concatenation / f-strings with user-supplied filters | **SQL injection** (see §8.2) |
| Analysis execution | Threads inside the Flask process | Ties analysis load to web server lifecycle; no backpressure, no retry, no scaling |
| Config | `config.ini` read from disk | Not 12-factor; awkward in containers |
| Storage | Media on local filesystem; results in PostgreSQL | Local FS blocks horizontal scaling; fine for compose, not for K8s |
| Repo hygiene | `__pycache__` committed; `device_extractions_Android/Estrazione_1` sample extraction in tree | Must be purged/audited before going public (§8.1) |

Assets we keep and build on:

- The AI analyzers are **already containerized external services** with HTTP APIs.
- PostgreSQL result schema (`text`, `pii`, `password`, `process_status`) is a sound starting point; `process_status` already models async job tracking.
- Extraction logic for iOS (`ChatStorage.sqlite`, Manifest parsing via `iOSbackup`) and Android (`msgstore.db`) is proven and gets refactored, not rewritten.

---

## 3. Target Architecture

```
                        ┌────────────────────────────┐
                        │  frontend (React + Vite)   │
                        │  served by nginx           │
                        └─────────────┬──────────────┘
                                      │ HTTPS (JSON)
                        ┌─────────────▼──────────────┐
                        │  api  (FastAPI)            │
                        │  auth (JWT), REST, OpenAPI │
                        │  stateless — N replicas    │
                        └──┬─────────┬───────────┬───┘
             sync calls    │         │ enqueue   │
        ┌──────────────────▼─┐   ┌───▼────────┐  │
        │ extraction-service │   │ broker     │  │
        │ schema fingerprint │   │ RabbitMQ / │  │
        │ query registry     │   │ Redis      │  │
        │ media indexing     │   └───┬────────┘  │
        └──────────┬─────────┘       │ consume   │
                   │          ┌──────▼─────────┐ │
                   │          │ analysis-worker│ │  ← autoscaled (KEDA)
                   │          │ Celery/ARQ     │ │
                   │          │ text / audio / │ │
                   │          │ image stages   │ │
                   │          └──┬─────────┬───┘ │
                   │             │ HTTP    │     │
                   │   ┌─────────▼──┐  ┌───▼─────▼──────┐
                   │   │ analyzer   │  │ report-service │
                   │   │ sidecars:  │  │ PDF + RFC 3161 │
                   │   │ DeepPass,  │  │ TSA signing    │
                   │   │ Whisper,   │  └───────┬────────┘
                   │   │ Tesseract, │          │
                   │   │ LAVIS      │          │
                   │   └────────────┘          │
        ┌──────────▼──────────┐     ┌──────────▼─────────┐
        │ PostgreSQL          │     │ MinIO / S3         │
        │ results, jobs, auth │     │ evidence media,    │
        └─────────────────────┘     │ generated reports  │
                                    └────────────────────┘
```

### Service responsibilities

| Service | Source (today) | Responsibility | Scaling |
|---|---|---|---|
| `frontend` | `templates/`, `assets/` → rewritten in React + Vite + TypeScript | UI only; talks to `api` via generated OpenAPI client | CDN/replicas, trivial |
| `api` | route layer of `main.py` | AuthN/Z, case & evidence management, job submission, results querying, progress (SSE/WebSocket) | HPA on CPU/RPS |
| `extraction-service` | `extractionIOS.py`, `extractionAndroid.py`, `repository/android_query.py`, iOS queries from `globalConstants.py` | Open evidence DBs read-only, fingerprint schema, run versioned queries, index media into object storage | Few replicas; I/O bound |
| `analysis-worker` | `services/*.py`, threading logic in `main.py` | Consume analysis tasks; call analyzer sidecars / cloud APIs; persist results | **KEDA on queue depth** |
| `report-service` | `reporting.py`, `certification.py` | Generate PDF, TSA timestamp, hash chain, zip | Queue-driven, scale-to-zero capable |
| analyzer sidecars | already external images | DeepPass, Whisper ASR, Tesseract, LAVIS | Optional profiles; GPU node pool in K8s |

### Communication rules

- FE ↔ `api`: REST/JSON (OpenAPI spec is the contract; client generated for the SPA).
- `api` ↔ workers: **only through the broker** (no direct HTTP), so workers can scale/restart freely.
- Progress: workers update `process_status` in PostgreSQL; `api` streams it to the FE via SSE.
- Every service: health (`/healthz`, `/readyz`) and Prometheus `/metrics` endpoints.

### Suggested repo layout (monorepo)

```
/
├── services/
│   ├── api/                # FastAPI
│   ├── extraction/         # + schema registry (see §4)
│   ├── worker/             # analysis pipeline
│   └── report/
├── frontend/               # React + Vite + TS
├── libs/
│   └── forensicwace_core/  # shared models, DB session, utils
├── deploy/
│   ├── compose/            # docker-compose.yml + profiles
│   └── helm/forensicwace/  # chart, values, KEDA ScaledObjects
├── schemas/whatsapp/       # versioned query registry (see §4)
└── docs/
```

---

## 4. WhatsApp DB Schema Versioning

**Problem**: WhatsApp changes its SQLite schema across app versions (e.g. Android moved
from the legacy `messages` table to `message`/`chat`/`jid` with the `chat_view` view;
iOS renames/adds `Z*` columns across releases). Today the queries assume one specific
schema and fail opaquely on others.

**Design**: *fingerprint the evidence DB, then resolve the best-matching query pack.*

### 4.1 Fingerprinting

On evidence registration, `extraction-service` opens the SQLite file read-only
(`file:...?mode=ro&immutable=1` — never mutate evidence) and collects:

1. `PRAGMA user_version;`
2. Table + column inventory from `sqlite_master` / `PRAGMA table_info`.
3. Platform hints (filename `msgstore.db` vs `ChatStorage.sqlite`, Manifest metadata on iOS).

The fingerprint is matched against **schema descriptors** — one YAML file per known
schema generation:

```yaml
# schemas/whatsapp/android/2.23-modern.yaml
platform: android
id: android-modern-chatview
priority: 10
detect:
  required_tables: [message, chat, jid]
  required_columns:
    message: [chat_row_id, from_me, timestamp, text_data]
  optional_tables: [chat_view, message_location]
queries:
  chat_list:      chat_list.sql
  private_chat:   private_chat.sql
  group_list:     group_list.sql
  gps_locations:  gps_locations.sql
  blocked:        null            # lives in wa.db for this generation
capabilities:
  blocked_contacts: false
  view_once: true
```

Matching = highest-priority descriptor whose `required_*` all exist. Partial match
(some optional capabilities missing) is reported to the user as degraded support
instead of a crash. No match → structured error listing the tables found, which
becomes the template for contributing a new descriptor.

### 4.2 Query packs

- All SQL lives in `.sql` files next to the descriptor — **no SQL in Python**.
- Every query is **parameterized** (`:filter`, `:jid`) — fixes the injection issue by design.
- A pack for a new WhatsApp version = a new YAML + SQL files + a fixture DB for tests.
  Contributors never touch service code to add version support.

### 4.3 Compatibility test matrix

`schemas/whatsapp/fixtures/` holds tiny **synthetic** SQLite fixtures (schema-only + fake
rows, generated by script — never real data). CI runs every query pack against every
fixture and produces a support matrix published in the docs.

---

## 5. Async Analysis Pipeline

- Broker: **RabbitMQ** (compose profile can fall back to Redis for a lighter setup).
- Worker framework: **Celery** (mature, first-class RabbitMQ support, per-queue routing).
- Task granularity: one task per `(message, stage)` where stage ∈ {text-pii, password,
  ocr, caption, transcription, gpt}. Fine granularity → smooth autoscaling and cheap retries.
- Queues per stage (`q.text`, `q.audio`, `q.image`, `q.cloud`) so GPU-bound and
  rate-limited (cloud API) work scale independently.
- Idempotency: task key = `(process_id, msg_id, stage)`; results upserted, safe to retry.
- Progress: workers increment `process_status.analyzed_messages`; `api` exposes SSE.
- Failure policy: exponential backoff ×3 → dead-letter queue, visible in the UI.

---

## 6. Deployment

### 6.1 Tier 1 — Docker Compose (developer & small-lab default)

`deploy/compose/docker-compose.yml` with **profiles**:

- `core`: postgres, rabbitmq, minio, api, extraction, worker, report, frontend(nginx).
- `analyzers-local`: deeppass, whisper, tesseract, lavis.
- Cloud analyzers configured purely via env vars — no containers needed.

Acceptance: `docker compose --profile core --profile analyzers-local up` gives a fully
working stack on a laptop; `.env.example` documents every variable.

### 6.2 Tier 2 — Kubernetes (Helm)

- Chart in `deploy/helm/forensicwace` (postgres/minio/rabbitmq as optional subcharts,
  or bring-your-own via values).
- `api`: Deployment + HPA (CPU/RPS).
- `analysis-worker`: Deployment + **KEDA `ScaledObject` on RabbitMQ queue length**
  (queue depth is the honest signal for batch forensic workloads; CPU is not).
  `report-service` can scale to zero.
- Analyzer sidecars on an optional GPU node pool (`nodeSelector`/taints in values).
- Evidence & media on S3-compatible storage (MinIO in-cluster or external S3) —
  no RWX volumes needed by design.
- Observability: Prometheus scrape annotations, Grafana dashboard JSON in the chart,
  structured JSON logs.

---

## 7. Configuration & Data

- 12-factor: all config via **environment variables** (pydantic-settings), `.env` for
  local dev. `config.ini` is removed; a small shim can translate it during migration.
- PostgreSQL migrations managed with **Alembic** from day one.
- Add `evidence` / `case` tables: today the extraction folders on disk are the implicit
  registry; they become first-class records (path/S3 key, hashes SHA256+MD5 at intake,
  fingerprint id, chain-of-custody notes).

---

## 8. Security & Open-Source Hygiene

### 8.1 Before the repo goes public (blocking)

1. **Purge sample extraction data** (`src/forensicWace_SE/device_extractions_Android/Estrazione_1`,
   any iOS UDID folders): audit for real personal data; rewrite git history
   (`git filter-repo`) if anything real was ever committed — deleting in a new commit is not enough.
2. Remove `__pycache__` from the tree; proper `.gitignore`.
3. `config.ini` currently holds placeholders only — keep it that way by deleting it in
   favor of `.env.example`, and add secret scanning (gitleaks) to CI.
4. Add `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.

### 8.2 Code-level

- **SQL injection**: user filters are concatenated into queries (Android
  `android_query.py`, iOS `queryPrivateChatCountersPT1 + filter + PT2` in
  `globalConstants.py`). Fixed structurally by the parameterized query packs (§4.2).
- **Evidence integrity**: open evidence SQLite strictly read-only/immutable; hash at
  intake and re-verify before report generation (extends the existing RFC 3161 work).
- **AuthN/Z**: JWT-based login in `api`; the `users` table finally gets used. Analyzer
  sidecars sit on an internal network, never exposed.
- **PII in logs**: never log message content; log IDs only. Results DB contains PII by
  nature → document at-rest encryption expectations for operators.

---

## 9. Roadmap

| Phase | Deliverable | Definition of done |
|---|---|---|
| **0. OSS hygiene** | Clean public-ready repo | §8.1 complete; CI (ruff + pytest + gitleaks) green; history audited |
| **1. API-first refactor** | FastAPI `api` + `libs/forensicwace_core`; `hostsData`/`remote_addr` state removed; env-var config; Dockerfiles + compose `core` profile | Full current feature set usable via documented REST API; `docker compose up` works |
| **2. React frontend** | `frontend/` SPA (React+Vite+TS), OpenAPI-generated client, nginx image | Feature parity with Jinja UI; Jinja templates deleted |
| **3. Async pipeline** | RabbitMQ + Celery workers; stage queues; SSE progress | Analysis survives api restarts; retry + DLQ observable in UI |
| **4. Schema registry** | §4 fingerprinting + query packs + synthetic fixtures + CI matrix | Current iOS/Android schemas ported to packs; unknown schema yields actionable report |
| **5. Kubernetes** | Helm chart + KEDA autoscaling + observability | Deploys on a stock k3s/EKS cluster; workers scale on queue depth in a load test |

Phases 3 and 4 are independent and can run in parallel. Each phase is a normal PR
series on `main` — no long-lived rewrite branch.

---

## 10. Technology Choices (summary)

| Concern | Choice | Why |
|---|---|---|
| API framework | FastAPI | OpenAPI for free (drives the FE client), pydantic validation, async |
| Frontend | React + Vite + TypeScript | Chosen by maintainer; largest contributor pool |
| Broker | RabbitMQ | Mature routing/DLQ; first-class KEDA scaler |
| Workers | Celery | Battle-tested, per-queue concurrency control |
| Object storage | MinIO / any S3 | Removes shared-FS requirement; same API in compose and K8s |
| Migrations | Alembic | Standard for SQLAlchemy (already a dependency) |
| Autoscaling | KEDA (workers) + HPA (api) | Queue depth is the correct scaling signal for batch analysis |
| Packaging | Monorepo, one image per service | Atomic cross-service changes while the team is small |
