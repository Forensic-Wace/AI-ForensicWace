# Forensic Wace

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20+%20Vite-61dafb.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue.svg)](https://www.postgresql.org/)

> **AI-powered forensic analysis platform for WhatsApp databases from iOS & Android devices — REST API, React web UI, containerized microservices.**

Born as a Bachelor's thesis project in Computer Forensics at the University of
Bari and now evolving into an open-source, production-oriented platform. The
architecture and roadmap live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Capabilities

- 📊 **Chat analysis**: chat lists, private and group chats, GPS locations, blocked contacts, media statistics — from iOS (`ChatStorage.sqlite`) and Android (`msgstore.db`) extractions
- 🔒 **Evidence-safe by design**: evidence databases are opened strictly read-only (`mode=ro&immutable=1`); SHA256/MD5 fingerprinting at access
- 🤖 **AI analyzers** (each optional, local or cloud):
  - PII: Microsoft Presidio, StarPII (HuggingFace), Azure Text Analytics, OpenAI GPT assistant
  - Passwords: DeepPass (BiLSTM)
  - Audio: Whisper ASR or Azure Speech-to-Text
  - Images: Tesseract OCR + LAVIS captioning, or Azure Computer Vision
- 📄 **Anti-tamper reports**: PDF exports with RFC 3161 trusted timestamps and verification
- 🌐 **Stateless REST API** (FastAPI, OpenAPI docs at `/docs`) + **React web UI**

## Architecture (current)

```
[frontend]  React + Vite, served by nginx      :3000
     │ /api (proxy)
[api]       FastAPI — stateless REST           :8080
     ├── forensicwace_core  (extraction, analysis pipeline, reporting)
     ├── [postgres]         analysis results & process tracking
     └── analyzer sidecars  DeepPass · Whisper · Tesseract · LAVIS (optional)
```

Next phases: async pipeline (RabbitMQ + workers, KEDA autoscaling), WhatsApp
schema-version registry, Helm chart. See the [roadmap](docs/ARCHITECTURE.md#9-roadmap).

## Quick start (Docker)

```bash
git clone https://github.com/Forensic-Wace/AI-ForensicWace.git
cd AI-ForensicWace

# Evidence goes under ./data (gitignored — NEVER commit evidence):
#   data/device_extractions_IOS/<UDID>/...
#   data/device_extractions_Android/<extraction_name>/msgstore.db

docker compose -f deploy/compose/docker-compose.yml --profile core up --build
# Web UI:   http://localhost:3000
# API docs: http://localhost:8080/docs

# Optional local AI analyzers (Whisper + Tesseract):
docker compose -f deploy/compose/docker-compose.yml --profile core --profile analyzers-local up
```

DeepPass and LAVIS require a local image build — see the commented services in
[deploy/compose/docker-compose.yml](deploy/compose/docker-compose.yml).

## Local development

**Backend**

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e "libs/forensicwace_core[postgres]" -e services/api
cp .env.example .env                              # configure FW_* variables
uvicorn forensicwace_api.main:app --reload --port 8080
```

**Frontend**

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8080
```

**Tests & lint**

```bash
pip install pytest httpx ruff
pytest libs/forensicwace_core/tests services/api/tests
ruff check libs/ services/
```

## Configuration

Everything is configured through `FW_*` environment variables (12-factor); a
`.env` file is honored in development. See [.env.example](.env.example) for
the full annotated reference: PostgreSQL URL, evidence directories, analyzer
endpoints and keys, TSA certificate, feature toggles.

Cloud analyzers (Azure, OpenAI) are **disabled by default** and activate only
when both their toggle (`FW_USE_*`) and credentials are set.

## Contributing

Contributions are very welcome — WhatsApp schema descriptors most of all.
Read [CONTRIBUTING.md](CONTRIBUTING.md) first, in particular the golden rules:
**never commit evidence data, never commit secrets**.

## License

MIT — see [LICENSE](LICENSE).

## ⚠️ Disclaimer

**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY ARISING FROM THE USE OF THE SOFTWARE.**

This tool is intended for **lawful forensic analysis** by authorized
professionals. The authors assume no liability for unauthorized access to
systems or data, privacy violations, legal consequences of improper use, or
wrong analysis results. Deploy only on trusted lab networks — authentication
is not yet enforced (see [SECURITY.md](SECURITY.md)).

## Acknowledgments

- **University of Bari** — original thesis project support
- **Microsoft, OpenAI, HuggingFace** — AI/ML technology providers
- **Open-source community** — Presidio, DeepPass, LAVIS, Whisper, Tesseract

---

**⭐ Star us on GitHub if you find this project useful!**
