# Analyzer Marketplace — design & tracking

**Status**: phase A complete (2026-07-11) — phases B and C not started
**Depends on**: phases 0–6 complete (see [ARCHITECTURE.md](ARCHITECTURE.md) §9)
**Goal**: analyzers become *installable at runtime* — browsed from a catalog,
registered in the database, run as containers provisioned on demand — instead
of being hardcoded in the core library and baked into the images.

---

## 1. Motivation — the current state

Three integration styles coexist today, all wired in code:

| Style | Analyzers | Where the coupling lives |
|---|---|---|
| In-process Python | Presidio, StarPII | pip extras baked into images (`CORE_EXTRAS`), lazy imports |
| Local HTTP sidecars | DeepPass, Whisper, Tesseract, LAVIS | one **bespoke adapter each** in `analysis/analyzers/` (different request/response formats) |
| Cloud SaaS | Azure PII/S2T/CV, OpenAI GPT | SDKs + keys + `FW_USE_*` toggles |

Adding one analyzer currently touches **~7 places** and requires an image
rebuild:

1. adapter module in `libs/forensicwace_core/forensicwace_core/analysis/analyzers/`
2. registry dicts in [`analyzers/__init__.py`](../libs/forensicwace_core/forensicwace_core/analysis/analyzers/__init__.py) (`TEXT_ANALYZERS`, `STATUS_CHECKS`)
3. settings fields in [`config.py`](../libs/forensicwace_core/forensicwace_core/config.py)
4. `.env.example`
5. `deploy/compose/docker-compose.yml` (service + env)
6. Helm chart (values + env wiring)
7. hardcoded checkbox arrays in [`AnalyzePage.tsx`](../frontend/src/pages/AnalyzePage.tsx)

Additional wrinkle: the media keys `S2T` and `image_OCR` are not analyzers but
*capabilities* whose implementation is picked from settings at call time
([`speech.py`](../libs/forensicwace_core/forensicwace_core/analysis/analyzers/speech.py):
Azure if enabled, else Whisper). The marketplace model makes this explicit.

What already works in our favor:

- staged pipeline with per-stage queues (`media` → `text`), retries + DLQ,
  KEDA scaling on queue depth — the dispatch layer does not change
- per-analyzer health checks and a status page (`GET /api/v1/analyzers/status`)
- a dynamic-registry pattern proven by the projects feature (Postgres table +
  CRUD + UI)

## 2. Target architecture

```
[catalog]     signed index of analyzer manifests (git/OCI)      — phase B
    │  browse / install
[registry]    `analyzers` table: installed analyzers, config    — phase A
    │  resolve by capability
[dispatch]    Celery stages (unchanged) → generic HTTP adapter  — phase A
    │  POST /analyze
[runtime]     analyzer containers, scale-to-zero, no egress     — phase C
```

Key model change — **capabilities, not hardcoded names**. An analysis request
selects capabilities (`pii`, `password`, `transcription`, `ocr`, `caption`);
the registry resolves which installed analyzers provide them. The pipeline
stage (media vs text queue) derives from the capability.

## 3. Analyzer contract v1

Any container implementing this REST contract is installable. One generic
adapter in core replaces every bespoke one. Draft — to be frozen in phase A:

```
GET /manifest
→ 200 {
    "contract": "fw-analyzer/1",
    "key": "deeppass",                     # unique, stable
    "name": "DeepPass password detector",
    "version": "1.2.0",
    "capabilities": ["password"],           # pii|password|transcription|ocr|caption
    "input": "text",                        # text | audio | image
    "config_schema": { ... JSON Schema ... },  # operator-facing options
    "resources": {"cpu": "500m", "memory": "2Gi", "gpu": false},
    "trust": "local"                        # local (no egress) | cloud (data leaves)
  }

GET /healthz
→ 200 {"status": "ok"}                      # optional: self-test detail

POST /analyze                               # input=text → JSON body
  {"text": "...", "config": {...}}
→ 200 {"findings": [{"kind": "password", "value": "...", "entity_type": null,
                     "confidence": 0.93}]}

POST /analyze                               # input=audio|image → multipart
  file=<bytes>, config=<json>
→ 200 {"enrichment": {"transcription": "..."}}      # or ocr_text / caption
```

Rules:

- evidence reaches the analyzer **only through the request payload** — never
  volume mounts;
- responses are versioned by the manifest (`version` + image digest recorded
  with every finding — see §4);
- existing built-in analyzers (Presidio, StarPII, Azure, GPT) stay in-process
  as registry entries with `type=builtin`; existing sidecars are conformed to
  the contract (thin proxy or upstream patch) as `type=http`.

## 4. Data model

New table `analyzers` (same pattern as `projects`):

| Column | Notes |
|---|---|
| `key` (pk) | stable id, what analysis requests reference |
| `name`, `version` | from the manifest |
| `type` | `builtin` \| `http` |
| `capabilities` | list — drives UI grouping and stage routing |
| `endpoint` | http type only |
| `image`, `image_digest` | provenance + phase C provisioning |
| `trust` | `local` \| `cloud` — gates per-analyzer consent (generalizes Pay2Use) |
| `config` | JSON, validated against manifest `config_schema` |
| `enabled` | soft switch |

Provenance (chain of custody): `Finding.source` today is a bare string
(`"deeppass_model"`). Findings must additionally record **analyzer version +
image digest** so reports can state exactly which software produced which
finding — reproducibility for court use is a first-class marketplace feature.

## 5. Security requirements (non-negotiable)

Evidence content (messages, audio, images — PII by definition) flows into
analyzer containers. Third-party analyzer = third-party code seeing evidence.

- [ ] catalog entries signed (cosign); installs pinned to `sha256:` digests, never tags
- [ ] default-deny **egress** NetworkPolicy on every `trust=local` analyzer
- [ ] no evidence volume mounts into analyzer pods (payload-only input)
- [ ] resource requests/limits from the manifest; non-root, read-only rootfs
- [ ] `trust=cloud` analyzers require explicit per-analyzer operator consent in the UI
- [ ] docker-socket provisioning (compose) stays **off by default** behind a flag — mounting `docker.sock` is effectively host root

## 6. Delivery phases

### Phase A — contract + dynamic registry ✅ *(shipped 2026-07-11)*

- [x] contract v1 frozen: [analyzer-contract.md](analyzer-contract.md) + pydantic models (`analysis/contract.py`) + generated JSON Schemas in `schemas/analyzer/` (sync enforced by test)
- [x] `analyzers` table (§4); DDL now under Alembic (baseline `0001` freezes the phase-7A schema; `init_db` runs `upgrade head` and adopts pre-Alembic databases)
- [x] generic HTTP adapter (`analysis/analyzers/http_analyzer.py`); capability-based resolution in `analysis/registry.py` — `S2T`/`image_OCR` survive as legacy aliases expanding to concrete keys
- [x] built-ins seeded as `type=builtin` rows at API startup — **10** of them: the media providers (whisper, microsoft_s2t, tesseract, lavis, microsoft_vision) became first-class analyzers, not settings-picked
- [x] REST: `GET /analyzers`, `GET /analyzers/status` (same URL as before), `POST /analyzers` (BYO container, manifest fetched and authoritative), `PATCH /analyzers/{key}`, `DELETE /analyzers/{key}` (builtin → 409, disable instead)
- [x] AnalyzePage + StatusPage read the dynamic list (hardcoded arrays removed); analysis submit validates keys (unknown/disabled → 422)
- [x] finding provenance: `analyzer_version` + `analyzer_digest` on PII/password rows, surfaced in results API and UI
- [x] tests: contract validation, MockTransport adapter roundtrip, alias/capability resolution, registry CRUD, full analysis with an external analyzer persisting provenance (21 new tests)

### Phase B — catalog + marketplace UI

- [ ] `catalog.json` format + signature verification; seed catalog with DeepPass, Whisper, Tesseract, LAVIS manifests
- [x] conform the four existing sidecars — done via `services/analyzer-shim`: one env-configured proxy image (`FW_SHIM_TARGET` = deeppass | whisper | tesseract | lavis) translating fw-analyzer/1 into each sidecar's native API; wired into the compose `analyzers-local` profile, registered at runtime through `POST /analyzers`
- [ ] Marketplace page: browse catalog, install (→ registry), configure (render `config_schema`), uninstall, health badges
- [ ] trust-tier consent UX (`local` vs `cloud` clearly separated)

### Phase C — orchestrated runtimes ("spawn all'evenienza")

- [ ] k8s provisioner: Deployment + Service + NetworkPolicy generated from the manifest at install time
- [ ] scale-to-zero at **analysis granularity**: API scales required analyzers 0→1 *before* dispatching to the queue (it knows the requested list at submit); idle reaper returns them to 0 after N minutes
- [ ] compose provisioner via docker socket, opt-in flag only
- [ ] GPU scheduling (`nodeSelector`/tolerations from manifest `resources.gpu`)

## 7. Rejected approaches

| Approach | Why not |
|---|---|
| Per-invocation containers (k8s Job per message/batch) | Whisper/LAVIS/StarPII load models for 10s of seconds–minutes; analyses fan out to thousands of messages — cold starts would dominate. Long-running + scale-to-zero gives the same "on demand" economics without the latency. |
| KEDA HTTP add-on / Knative from day one | Analysis-granularity scaling (the API knows the analyzer list at submit) is simpler and sufficient; revisit only if per-request wake-up becomes a real need. |
| Python plugin packages (pip-installable analyzers) | Keeps the rebuild problem, runs third-party code inside the worker process (no isolation), dependency conflicts (torch versions). Containers + HTTP is the isolation boundary we already use. |
| docker.sock provisioning by default in compose | Host-root equivalent; unacceptable default for a forensics platform. |

## 8. Open questions

- [ ] Catalog hosting: git repo in the org (simplest, PR-reviewed) vs OCI artifacts (digest-native)? — leaning git first, OCI later
- [ ] Multi-analyzer per capability: run all installed providers of a capability or force the operator to pick one? (today: settings priority picks one)
- [ ] Contract for batch endpoints (`POST /analyze/batch`) to amortize HTTP overhead on large analyses — v1 or v1.1?
- [ ] Where analyzer configs holding secrets (e.g. a licensed model key) live: registry `config` JSON vs k8s Secret reference
