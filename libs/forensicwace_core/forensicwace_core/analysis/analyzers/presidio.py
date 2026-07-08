"""Microsoft Presidio local PII analyzer (rule-based + ML hybrid)."""

from functools import lru_cache

from ...config import get_settings
from ..types import AnalyzerStatus, Finding

SCORE_THRESHOLD = 0.5


@lru_cache
def _engine():
    from presidio_analyzer import AnalyzerEngine

    from .url_recognizer import UrlRecognizer

    engine = AnalyzerEngine()
    recognizers_file = get_settings().presidio_recognizers_file
    if recognizers_file:
        engine.registry.add_recognizers_from_yaml(str(recognizers_file))
    engine.registry.add_recognizer(UrlRecognizer(supported_entities=["URL_NEW"]))
    return engine


def analyze(text: str) -> list[Finding]:
    results = _engine().analyze(text=text, language="en", score_threshold=SCORE_THRESHOLD)
    return [
        Finding(kind="pii", entity_type=r.entity_type, value=text[r.start : r.end], source="presidio")
        for r in results
    ]


def check_status() -> AnalyzerStatus:
    try:
        results = _engine().analyze(
            text="IT60X0542811101000000123456",
            entities=["IBAN_CODE"],
            language="en",
            score_threshold=SCORE_THRESHOLD,
        )
        ok = bool(results) and results[0].entity_type == "IBAN_CODE"
        return AnalyzerStatus("Presidio", ok, "Presidio is working" if ok else "Presidio did not detect a test IBAN")
    except Exception as exc:
        return AnalyzerStatus("Presidio", False, str(exc))
