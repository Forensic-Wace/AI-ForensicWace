# Forensic Wace analysis worker — build from the repository root:
#   docker build -f services/worker/Dockerfile .
#
# CORE_EXTRAS selects the analyzer stacks baked into the image (see
# libs/forensicwace_core/pyproject.toml): postgres | presidio | starpii | azure | openai

FROM python:3.12-slim

ARG CORE_EXTRAS=postgres

# ffmpeg converts voice notes to WAV before transcription
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/forensicwace_core /app/libs/forensicwace_core
COPY services/worker /app/services/worker
COPY assets /app/assets
COPY schemas /app/schemas

RUN pip install --no-cache-dir \
    "/app/libs/forensicwace_core[${CORE_EXTRAS}]" \
    /app/services/worker

ENV FW_DATA_DIR=/data \
    FW_ASSETS_DIR=/app/assets \
    FW_SCHEMAS_DIR=/app/schemas/whatsapp \
    FW_TSA_CERTIFICATE_FILE=/app/assets/reportCertificate/tsa.crt \
    FW_PRESIDIO_RECOGNIZERS_FILE=/app/assets/presidio_recognizers/recognizers.yaml
VOLUME /data

# Consumes every stage queue by default; split per-queue workers to scale
# stages independently (e.g. -Q media on a GPU node pool).
CMD ["celery", "-A", "forensicwace_worker.celery_app", "worker", "-Q", "control,media,text", "--concurrency=4", "--loglevel=INFO"]
