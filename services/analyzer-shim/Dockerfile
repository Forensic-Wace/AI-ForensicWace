# fw-analyzer/1 shim — wraps one historical sidecar in the standard contract.
# Build from the repository root:
#   docker build -f services/analyzer-shim/Dockerfile .
# Configure with FW_SHIM_TARGET (deeppass|whisper|tesseract|lavis) and
# FW_SHIM_TARGET_URL; then register the shim through the analyzer registry:
#   curl -X POST http://api:8080/api/v1/analyzers -H 'Content-Type: application/json' \
#        -d '{"endpoint": "http://<shim-host>:9300"}'

FROM python:3.12-slim

WORKDIR /app

COPY services/analyzer-shim /app/services/analyzer-shim

RUN pip install --no-cache-dir /app/services/analyzer-shim

EXPOSE 9300

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:9300/healthz').raise_for_status()"

CMD ["uvicorn", "--factory", "forensicwace_analyzer_shim.main:build", "--host", "0.0.0.0", "--port", "9300"]
