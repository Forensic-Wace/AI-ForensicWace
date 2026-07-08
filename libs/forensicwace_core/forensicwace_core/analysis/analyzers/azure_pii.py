"""Microsoft Azure Text Analytics PII detection."""

from functools import lru_cache

from ...config import get_settings
from ..types import AnalyzerStatus, Finding


@lru_cache
def _client():
    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential

    settings = get_settings()
    return TextAnalyticsClient(
        endpoint=settings.ms_pii_endpoint,
        credential=AzureKeyCredential(settings.ms_pii_key),
    )


def _configured() -> bool:
    settings = get_settings()
    return bool(settings.use_ms_pii and settings.ms_pii_endpoint and settings.ms_pii_key)


def analyze(text: str) -> list[Finding]:
    if not _configured():
        return []
    response = _client().recognize_pii_entities([text], language="en")
    findings = []
    for doc in response:
        if doc.is_error:
            continue
        for entity in doc.entities:
            findings.append(Finding(kind="pii", entity_type=entity.category, value=entity.text, source="microsoftPII"))
    return findings


def check_status() -> AnalyzerStatus:
    if not _configured():
        return AnalyzerStatus("MS PII", False, "Not enabled or not configured")
    try:
        response = _client().recognize_pii_entities(["example@email.com"], language="en")
        ok = response[0].entities[0].category.lower() == "email"
        return AnalyzerStatus("MS PII", ok, "Microsoft PII is working" if ok else "Unexpected response")
    except Exception as exc:
        return AnalyzerStatus("MS PII", False, str(exc))
