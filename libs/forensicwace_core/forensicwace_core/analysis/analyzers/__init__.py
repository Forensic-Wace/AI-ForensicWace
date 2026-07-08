"""Analyzer registry.

Text analyzers take a plain string and return :class:`Finding` objects; media
analyzers enrich a :class:`Message` in place. Heavy dependencies (torch,
transformers, presidio, Azure SDKs) are imported lazily inside each module so
the platform runs with any subset of analyzers installed and configured.
"""

from collections.abc import Callable

from ..types import AnalyzerStatus, Finding

# Registry keys are part of the public API contract (they are what clients
# send in the "analyzers" field of an analysis request).
TEXT_ANALYZERS: dict[str, Callable[[str], list[Finding]]] = {}
STATUS_CHECKS: dict[str, Callable[[], AnalyzerStatus]] = {}


def _register() -> None:
    from . import azure_pii, deeppass, gpt, presidio, speech, starpii, vision

    TEXT_ANALYZERS.update(
        {
            "presidio": presidio.analyze,
            "starpii": starpii.analyze,
            "deep_password": deeppass.analyze,
            "gpt": gpt.analyze,
            "microsoftPII": azure_pii.analyze,
        }
    )
    STATUS_CHECKS.update(
        {
            "presidio": presidio.check_status,
            "starpii": starpii.check_status,
            "deep_password": deeppass.check_status,
            "gpt": gpt.check_status,
            "microsoftPII": azure_pii.check_status,
            "S2T_microsoft": speech.check_status_microsoft,
            "S2T_whisper": speech.check_status_whisper,
            "vision_microsoft": vision.check_status_microsoft,
            "vision_tesseract": vision.check_status_tesseract,
            "vision_lavis": vision.check_status_lavis,
        }
    )


_register()


def run_text_analyzers(text: str, analyzer_names: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for name in analyzer_names:
        analyzer = TEXT_ANALYZERS.get(name)
        if analyzer is not None:
            findings.extend(analyzer(text))
    return findings


def all_statuses() -> list[AnalyzerStatus]:
    statuses = []
    for check in STATUS_CHECKS.values():
        try:
            statuses.append(check())
        except Exception as exc:  # a broken analyzer must never break the health page
            statuses.append(AnalyzerStatus(name=check.__module__.rsplit(".", 1)[-1], available=False, detail=str(exc)))
    return statuses
