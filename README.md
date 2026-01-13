# Forensic Wace - Server Edition
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Backend-Flask-green.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue.svg)](https://www.postgresql.org/)
[![GitHub](https://img.shields.io/badge/GitHub-ForensicWace-black.svg)](https://github.com/Forensic-Wace/AI-ForensicWace)

> **Advanced AI-powered multi-threaded forensic analysis platform for WhatsApp databases from iOS & Android devices with 7+ integrated AI analyzers**

---

## 📚 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Database Schema](#database-schema)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## 🎯 Overview

**Forensic Wace Server Edition** is an advanced, **multi-threaded forensic analysis platform** designed for analyzing WhatsApp databases from both iOS and Android devices. Originally developed as a Bachelor's thesis project in Computer Forensics at the University of Bari, it has evolved into a comprehensive tool used by forensic professionals.

The platform uniquely combines **open-source AI analyzers** (Presidio, DeepPass, StarPII, Tesseract, LAVIS, Whisper AI) with **cloud-based services** (Microsoft Azure Cognitive Services, OpenAI ChatGPT) to provide comprehensive forensic investigation capabilities.


### Core Capabilities

- 📊 **Advanced Chat Analysis**: Chats List, private chats, group chats, GPS locations, blocked contact and media files 
- 🤖 **AI Analyzers**: Multi-stage PII and sensitive data detection
- 🖼️ **Media Processing**: OCR (Tesseract/Azure CV), image captioning (LAVIS/Azure CV), and voice transcription (Whisper AI/Azure S2T)
- 🎬 **Multi-Threading**: Process multiple databases and messages simultaneously
- 🌐 **Web Interface**: Responsive User Friendly Bootstrap 5 frontend
- 🔒 **Anti-Tamper Reports**: RFC 3161 TSA-signed PDF reports with cryptographic verification

🧩 Project Origin
Forensic Wace was born from the fusion of two academic research projects originally developed as university theses in the field of digital and mobile forensics.
While this codebase may contain portions of experimental or non‑optimized code, it reflects the iterative and exploratory nature of research-oriented development. As such, some components may not follow production-grade standards or may require refinement — yet they represent innovative approaches and proof‑of‑concept implementations built for educational and research purposes.

The project integrates various techniques for forensic data extraction and analysis, including the use of open‑source AI modules for password detection, text analysis, and multimedia content understanding. Its main goal is to serve as a foundation for experimentation and idea sharing within the forensic research community.

Future work will focus on developing a morerobust and scalable Enterprise Edition, featuring an architecture based on microservices, RESTful APIs, and asynchronous message queues.
This next iteration will aim to provide high reliability, distributed processing, and integration capabilities suitable for production and enterprise environments while maintaining the spirit of academic transparency and open research.

In summary, Forensic Wace should be seen as a research‑grade platform — a living laboratory for testing innovative forensic techniques, data processing pipelines, and AI‑assisted analysis workflows.
Although not free from imperfections or bugs, it embodies a valuable contribution to the community: a hands‑on, open, and evolving tool designed to bridge the gap between academic exploration and real‑world investigative practice.


---

## ✨ Key Features

### 1. **Comprehensive Database Support**

**iOS**
- ✅ WhatsApp databases: `ChatStorage.sqlite`
- ✅ Profile pictures and chat media extraction from unencrypted backup
- ✅ Manifest.plist metadata parsing

**Android**
- ✅ WhatsApp databases: `msgstore.db`
- ✅ Chat media extraction

### 2. **Advanced Chat Analysis Module**

| Feature                       | Capability                                                                                        |
|-------------------------------|---------------------------------------------------------------------------------------------------|
| **Private Chats**             | Full chat extraction including media                                                              |
| **Group Chats**               | Member tracking, sender identification, deletion detection                                        |
| **GPS Locations**             | Coordinate extraction, Google Maps integration                                                    |
| **Blocked Contacts**          | Blocked contacts list extraction                                                                  |
| **Media Messages Statistics** | Total messages, deleted messages, media distribution                         |

### 3. **7-Stage AI-Powered PII Detection System**

#### Stage 1: Local Open-Source Analyzers

**Microsoft Presidio (Custom Recognizers)**
- Technology: Rule-based + ML hybrid
- Detectable Entities: Names, emails, phones, credit cards, IPs, dates, locations, and 50+ custom entity types
- Configuration: YAML-based custom recognizers
- Performance: Sub-millisecond per message

**DeepPass (Local Docker Service)**
- Technology: Bidirectional LSTM neural network
- Detection Scope: Passwords, credentials, API keys, access tokens
- Fork: [daniele96/DeepPass_RestApi](https://github.com/daniele96/DeepPass_RestApi) with `/api/text` endpoint

**StarPII (HuggingFace Transformers)**
- Technology: Named Entity Recognition (NER) with BERT
- Entities: Names, emails, passwords, IPs, usernames, addresses
- Model: `dslim/bert-base-multilingual-cased-ner-hrl`
- Inference: GPU-accelerated with CUDA support

#### Stage 2: Cloud-Based Enterprise Analyzers

**Microsoft Azure Text Analytics**
- PII Categories: 100+ pre-configured entity types
- Languages: 95+ supported languages
- Features: Entity linking, sentiment analysis, key phrase extraction
- Endpoint: Azure Cognitive Services API
- Batch Processing: Up to 1000 documents per request

**Microsoft Azure Speech-to-Text**
- Supported Formats: MP4, WAV
- Languages: Multi-language support with automatic detection
- Real-time Transcription: Low-latency audio processing
- Codec Support: Automatic format conversion via ffmpeg

**Microsoft Azure Computer Vision (OCR)**
- Text Extraction: 90+ languages supported
- Image Captioning: Contextual description generation with confidence scores
- Processing: Single-image

**OpenAI ChatGPT (GPT-4 Assistants)**
- Advanced PII Detection: 14+ entity types with contextual reasoning
- Custom Entity Types: User-defined pattern definitions
- Integration: OpenAI Assistants API with persistent threads


### 4. **Forensic Report Generation**

- **Format**: PDF with embedded metadata and digital signatures
- **Signature**: RFC 3161 TSA compliant timestamps
- **Anti-tampering**: hash verification, page integrity checks
- **Compression**: Auto-zip with pdf and certificate

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Web Frontend Layer                                │
│                        Bootstrap 5                                   │
│ [Chat List] [Private Chat] [Groups] [Locations] [Reports] [Settings] |
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP/REST
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Flask Backend Server                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ API Routes Layer (main.py)                                     │  │
│  │ - /IosHomepage, /AndroidHomepage, /ChatList, /PrivateChat      │  │
│  │ - /GroupList, /GroupChat, /GpsLocations, /BlockedContacts      │  │
│  │ - /Analyze, /GenerateReport, /Settings                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Extraction Layer (extractionIOS.py, extractionAndroid.py)      │  │
│  │ - Database parsing & decryption                                │  │
│  │ - SQL query execution                                          │  │
│  │ - Media file extraction                                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ AI Analysis Layer (services/*.py)                              │  │
│  │ ├─ Presidio (ExtractPiiService.py)                             │  │
│  │ ├─ DeepPass (deepPassClient.py)                                │  │
│  │ ├─ StarPII (starpii_Service.py)                                │  │
│  │ ├─ ChatGPT (chatgptService.py)                                 │  │
│  │ ├─ Azure Text (microsoftPIIExtractor.py)                       │  │
│  │ ├─ Audio S2T (AudioServices.py)                                │  │
│  │ └─ Image Analysis (ImageServices.py)                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Utilities & Helpers (utils.py, globalConstants.py)             │  │
│  │ - File hashing (SHA256, MD5)                                   │  │
│  │ - Time conversion (Apple 2001 reference)                       │  │
│  │ - Phone number formatting                                      │  │
│  │ - Config file management                                       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────┬──────────────────┬──────────────────┬──────────────────┬──────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌────────────────┐ ┌─────────────────┐ ┌──────────────┐ ┌─────────────┐
│  PostgreSQL    │ │ Local Services  │ │ Azure Cloud  │ │ OpenAI API  │
│  Database      │ │  (Docker)       │ │  Services    │ │ (ChatGPT)   │
│ • Chat data    │ │  • DeepPass     │ │ • PII Extract│ │ • GPT-4     │
│ • Analysis     │ │  • LAVIS        │ │ • Vision OCR │ │ • Assistants│
│ • Metadata     │ │  • Whisper AI   │ │ • S2T Audio  │ └─────────────┘
│ • Results      │ │  • Tesseract    │ └──────────────┘ 
└────────────────┘ └─────────────────┘ 
```

---

## 💻  Requirements

### Required Services

**Local - Mandatory**
- **PostgreSQL 12+** (main database)
- **Docker** (for containerized services)

**Local - Optional Docker Services** (for open-source AI analyzers)

All Docker services are **OPTIONAL**. Enable only the analyzers you need by selecting from the interface or in `config.ini` under `[Pay2UseAnalyzers]` section.

- **DeepPass API** - Password detection via BiLSTM
  - Repository: [daniele96/DeepPass_RestApi](https://github.com/daniele96/DeepPass_RestApi)
  - Fork of GhostPack/DeepPass with `/api/text` endpoint for raw text analysis
  - Threshold: 0.75 (increased from 0.5 for higher precision)
  - Endpoint: `http://localhost:5000`
  
- **LAVIS Image Captioning** - Image description generation
  - Repository: [daniele96/ImageCaption_lavis](https://github.com/daniele96/ImageCaption_lavis)
  - Uses LAVIS (Large-scale Adversarial Vision-Language Models)
  - Generates contextual captions for images
  - Endpoint: `http://localhost:7866`
  
- **Whisper AI** - Speech-to-Text transcription
  - Docker Hub: [onerahmet/openai-whisper-asr-webservice](https://hub.docker.com/r/onerahmet/openai-whisper-asr-webservice/)
  - OpenAI Whisper AI service with REST API
  - Supports multiple model sizes (tiny, base, small, medium, large)
  - Endpoint: `http://localhost:9000`
  
- **Tesseract OCR** - Optical Character Recognition
  - Docker Hub: [hertzg/tesseract-server](https://hub.docker.com/r/hertzg/tesseract-server)
  - OCR text extraction from images
  - Supports 100+ languages
  - Endpoint: `http://localhost:7865`

**Cloud Optional** (enable for enhanced analysis)
- **Microsoft Azure Cognitive Services** account
  - Text Analytics (PII extraction)
  - Computer Vision (OCR + image captioning)
  - Speech-to-Text (alternative to Whisper)
  
- **OpenAI API** account with GPT-4 access
  - ChatGPT Assistants API for advanced PII detection
  
- **HuggingFace** account for model access
  - StarPII NER model hosting

---

## 📦 Installation

### Prerequisites

```bash
# Python version check
python3 --version  # Should be 3.9 or higher

# PostgreSQL installation
# Windows: https://www.postgresql.org/download/windows/
# macOS: brew install postgresql@14
# Linux: sudo apt-get install postgresql postgresql-contrib

# Docker installation (for DeepPass)
# https://www.docker.com/products/docker-desktop

# System dependencies
# Ubuntu/Debian:
sudo apt-get install build-essential libpq-dev ffmpeg

# macOS:
brew install ffmpeg

# Windows:
dowload and install ffmpeg from https://ffmpeg.org/download.html
```

### Option 1: GitHub Clone (Recommended)

```bash
# Clone repository
git clone https://github.com/daniele96/Forensic-Wace-AI.git

cd ForensicWace-SE

# Create virtual environment
python3 -m venv venv

# Activate environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt

```

---

## 🔧 Configuration


### 1.System Configuration

**config.ini:**
```ini
[API]
# PostgreSQL Connection
databaseurl = postgresql://admin:password@localhost:5432/forensic_wace

# HuggingFace (for StarPII)
hftoken = hf_YOUR_HUGGINGFACE_TOKEN

# OpenAI ChatGPT
openaiapikey = sk-proj-YOUR_OPENAI_KEY
gtpassistantidextract = asst_YOUR_ASSISTANT_ID

# Local Docker Services
deeppassendpoint = http://localhost:5000

# Docker Service Endpoints (Optional)
audios2twhisperaserendpoint = http://localhost:9000
ocrtesseractendpoint = http://localhost:7865
imagecaptionlavisendpoint = http://localhost:7866

# Microsoft Azure Services
# PII Extractor
mspiiendpoint = https://YOUR_REGION.cognitiveservices.azure.com/
mspiikey = YOUR_AZURE_PII_KEY

# Speech-to-Text
mss2tkey = YOUR_AZURE_SPEECH_KEY
mss2tregion = eastus
mss2tlanguage = en-US

# Computer Vision (OCR + Captioning)
mscvendpoint = https://YOUR_REGION.cognitiveservices.azure.com/
mscvkey = YOUR_AZURE_CV_KEY
mscvlanguage = en

[Pay2UseAnalyzers]
mss2t = on
msazureocrandcaption = on
mspii = on
openaigpt = on
```

### 3. PostgreSQL Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE forensic_wace;"
```
```bash
# Create user, multiusers is not implemented yet but we need a record for saving all info extracted
psql -U postgres -c "INSERT INTO public.users(
	id, name, surname, address, comment)
	VALUES ('1', 'name', 'surname', 'address', 'comment');"
```
### 4. Docker Services Setup

**DeepPass Password Detection**

```bash
# Clone and run the fork
git clone https://github.com/daniele96/DeepPass_RestApi.git
cd DeepPass_RestApi
docker-compose up -d

# Service runs on http://localhost:5000
# Endpoint: POST /api/text
```

**LAVIS Image Captioning**

```bash
# Clone and run the fork
git clone https://github.com/daniele96/ImageCaption_lavis.git
cd ImageCaption_lavis
docker build -t lavis-service:latest .
docker run -d \
  -p 7866:5000 \
  --name lavis-service \
  lavis-service:latest

# Service runs on http://localhost:7866
```

**Whisper ASR Speech-to-Text**

```bash
# Pull official Whisper ASR service
docker pull onerahmet/openai-whisper-asr-webservice:latest

docker run -d \
  -p 9000:9000 \
  -e ASR_MODEL=base \
  -e ASR_ENGINE=openai_whisper \
  --name whisper-asr \
  onerahmet/openai-whisper-asr-webservice:latest

# Service runs on http://localhost:9000
# Endpoint: POST /asr
```

**Tesseract OCR**

```bash
# Pull official Tesseract server
docker pull hertzg/tesseract-server:latest

docker run -d \
  -p 7865:8884 \
  --name tesseract-server \
  hertzg/tesseract-server:latest

# Service runs on http://localhost:7865
# Endpoint: POST /v1/ocr
```

---

## 🚀 Quick Start

### Step 1: Prepare WhatsApp Database

**For iOS:**
```
Place backup files in: device_extractions_IOS/<UDID>
```

**For Android:**
```
Place backup files in: device_extractions_Android/device_name/
├── msgstore.db
└── Media/  (optional)
```

### Step 2: Start Server

```bash
# Activate environment
source venv/bin/activate  # or: venv\Scripts\activate

# Run Flask server
python -m forensicWace_SE.app

```

### Step 3: Access Web Interface

Open browser: `http://localhost:5000`

1. **Select Backup**: Click "Select iOS/Android Backup"
2. **Choose Device**: Select extracted device from list
3. **View Chats**: Browse extracted messages
4. **Run Analysis**: Apply AI analyzers to messages
5. **Generate Report**: Export findings as PDF

---



## 📊 Database Schema

### PostgreSQL Tables

**Text Table**
```sql
CREATE TABLE text (
    id SERIAL PRIMARY KEY,
    msg_id INTEGER NOT NULL,
    process_id VARCHAR(255),
    text TEXT NOT NULL,
    user_id VARCHAR(255),
    date TIMESTAMP,
    audio_path VARCHAR(500),
    audio_stt TEXT,
    image_path VARCHAR(500),
    image_caption TEXT,
    image_ocr TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PII Results (One-to-Many relationship)
CREATE TABLE pii (
    id SERIAL PRIMARY KEY,
    text_id INTEGER REFERENCES text(id),
    type VARCHAR(100),      -- Entity type (EMAIL, PHONE, CREDIT_CARD, etc.)
    value TEXT,
    source VARCHAR(50),     -- Analyzer name (presidio, starpii, gpt, azure_pii)
    score FLOAT,           -- Confidence score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password Detection Results
CREATE TABLE password (
    id SERIAL PRIMARY KEY,
    text_id INTEGER REFERENCES text(id),
    password TEXT,
    source VARCHAR(50),     -- deeppass, gpt, etc.
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Process Status Tracking
CREATE TABLE process_status (
    id SERIAL PRIMARY KEY,
    process_id VARCHAR(255) UNIQUE,
    status VARCHAR(50),     -- Pending, Analyzing, Completed, Error
    details TEXT,
    progress_percent INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    total_messages INTEGER,
    analyzed_messages INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---




## 👥 Development


### Adding New Analyzers

To add a new AI analyzer:

1. Create service file in `src/forensicWace_SE/services/newAnalyzer.py`
2. Implement `check_status()` function for health check
3. Implement main analysis function
4. Add case in `textServices.py` match statement
5. Add configuration in `config.ini`
6. Add UI toggle in `Settings.html`

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**IMPORTANT - READ CAREFULLY BEFORE USE**


### Software Disclaimer

**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.**

**IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**

### No Liability for Misuse

The authors assume no liability for:
- Unauthorized access to systems or data
- Privacy violations or data breaches
- Legal consequences of improper use
- Data loss or corruption
- Performance issues in specific environments
- Wrong analysis results

---

### Acknowledgments

- **University of Bari** - Original thesis project support
- **Microsoft, OpenAI, HuggingFace** - AI/ML technology providers
- **Open-source community** - Presidio, DeepPass, LAVIS, and other projects

---

**⭐ Star us on GitHub if you find this project useful!**
