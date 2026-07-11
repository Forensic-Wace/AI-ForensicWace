# fw-analyzer/1 — the analyzer contract

Any container exposing the three endpoints below can be installed into
Forensic Wace at runtime (`POST /api/v1/analyzers` with its base URL) and
used in analyses like the built-in analyzers. No platform rebuild, no
adapter code: the platform ships one generic client
(`forensicwace_core.analysis.analyzers.http_analyzer`).

Source of truth: the pydantic models in
[`forensicwace_core/analysis/contract.py`](../libs/forensicwace_core/forensicwace_core/analysis/contract.py).
Machine-readable schemas (generated from those models, kept in sync by a
test): [`schemas/analyzer/`](../schemas/analyzer/).

## Concepts

| Term | Values | Meaning |
|---|---|---|
| capability | `pii`, `password`, `transcription`, `ocr`, `caption` | What the analyzer detects/produces. Drives UI grouping and pipeline routing. |
| input | `text`, `audio`, `image` | What one `/analyze` call consumes. Must match the capabilities (`pii`/`password` → text, `transcription` → audio, `ocr`/`caption` → image). |
| trust | `local`, `cloud` | `local` promises evidence never leaves the deployment. `cloud` analyzers require explicit operator consent. |

An analyzer has exactly one `input` type. Text analyzers return **findings**;
media analyzers (audio/image) return **enrichment** that the platform feeds
into the text stage.

## Endpoints

### `GET /manifest`

Self-description; fetched at registration time and authoritative for
key/name/capabilities. Schema: [`manifest.schema.json`](../schemas/analyzer/manifest.schema.json).

```json
{
  "contract": "fw-analyzer/1",
  "key": "my_detector",
  "name": "My credit-card detector",
  "version": "1.0.0",
  "capabilities": ["pii"],
  "input": "text",
  "config_schema": {
    "type": "object",
    "properties": { "min_confidence": { "type": "number", "default": 0.5 } }
  },
  "resources": { "cpu": "500m", "memory": "1Gi", "gpu": false },
  "trust": "local"
}
```

- `key`: `^[a-z][a-z0-9_-]{1,63}$`, globally unique, stable across versions —
  it is what analysis requests and stored findings reference.
- `config_schema`: JSON Schema of the operator-facing options; the platform
  stores the chosen config and sends it with every `/analyze` call.
- `resources`: scheduling hints, advisory in phase A (used by the phase-C
  provisioner).

### `GET /healthz`

`200` when ready to analyze. Anything else marks the analyzer unavailable on
the status page.

### `POST /analyze`

Schema of the response: [`analyze-response.schema.json`](../schemas/analyzer/analyze-response.schema.json).

**Text analyzers** (`input: text`) receive JSON:

```json
{ "text": "il mio iban è IT60X0542811101000000123456", "config": { "min_confidence": 0.5 } }
```

and answer with findings:

```json
{
  "findings": [
    { "kind": "pii", "value": "IT60X0542811101000000123456",
      "entity_type": "IBAN_CODE", "confidence": 0.98 }
  ]
}
```

**Media analyzers** (`input: audio` or `image`) receive `multipart/form-data`
with the evidence file (`file`) and the config as a JSON string (`config`),
and answer with enrichment (only the fields they produce):

```json
{ "enrichment": { "transcription": "ci vediamo alle nove" } }
```

`ocr_text` and `caption` are the image counterparts.

## Rules

1. **Payload-only evidence.** Evidence reaches the analyzer exclusively
   through `/analyze` request bodies. Analyzers must not persist evidence
   beyond the request lifetime.
2. **Stateless.** Every `/analyze` call is independent; the platform retries
   failed calls (3 attempts, exponential backoff) and may call concurrently.
3. **No egress for `trust: local`.** Deployment enforces this with network
   policy in Kubernetes (phase C); declaring `local` while calling out is a
   contract violation.
4. **Provenance.** The platform records `key`, manifest `version` and image
   digest with every finding (chain of custody). Bump `version` on any change
   that can alter results.
5. **Timeouts.** The platform waits up to 120 s per `/analyze` call.

## Minimal example (FastAPI)

```python
from fastapi import FastAPI

app = FastAPI()
MANIFEST = {
    "contract": "fw-analyzer/1", "key": "shouty", "name": "Shouty word detector",
    "version": "1.0.0", "capabilities": ["pii"], "input": "text", "trust": "local",
}

@app.get("/manifest")
def manifest(): return MANIFEST

@app.get("/healthz")
def healthz(): return {"status": "ok"}

@app.post("/analyze")
def analyze(body: dict):
    words = [w for w in body["text"].split() if w.isupper() and len(w) > 3]
    return {"findings": [{"kind": "pii", "value": w, "entity_type": "SHOUTY"} for w in words]}
```

Run it, then install it:

```bash
curl -X POST http://localhost:8080/api/v1/analyzers \
  -H 'Content-Type: application/json' \
  -d '{"endpoint": "http://my-analyzer:9009"}'
```

It now appears in `GET /api/v1/analyzers`, in the AI-analysis page checkboxes
and on the status page; analyses can request its key like any built-in.
