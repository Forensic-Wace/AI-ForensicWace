# Forensic Wace API — build from the repository root:
#   docker build -f services/api/Dockerfile .
#
# CORE_EXTRAS selects the analyzer stacks baked into the image:
#   postgres (default) | presidio | starpii (pulls torch, large!) | azure | openai
#   e.g. --build-arg CORE_EXTRAS=postgres,presidio,azure,openai

FROM python:3.12-slim

ARG CORE_EXTRAS=postgres

# ffmpeg converts voice notes to WAV before transcription
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/forensicwace_core /app/libs/forensicwace_core
COPY services/api /app/services/api
COPY assets /app/assets

RUN pip install --no-cache-dir \
    "/app/libs/forensicwace_core[${CORE_EXTRAS}]" \
    /app/services/api

# Evidence extractions are mounted here (see FW_DATA_DIR)
ENV FW_DATA_DIR=/data \
    FW_ASSETS_DIR=/app/assets \
    FW_TSA_CERTIFICATE_FILE=/app/assets/reportCertificate/tsa.crt \
    FW_PRESIDIO_RECOGNIZERS_FILE=/app/assets/presidio_recognizers/recognizers.yaml
VOLUME /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/healthz').raise_for_status()"

CMD ["uvicorn", "forensicwace_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
