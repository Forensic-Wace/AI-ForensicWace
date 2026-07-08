"""StarPII named-entity PII detection (HuggingFace ``bigcode/starpii``)."""

from functools import lru_cache

from ...config import get_settings
from ..types import AnalyzerStatus, Finding

MODEL = "bigcode/starpii"


@lru_cache
def _pipeline():
    from transformers import pipeline

    return pipeline("token-classification", model=MODEL, token=get_settings().hf_token)


def _group_entities(text: str, outputs: list[dict]) -> dict[str, list[str]]:
    """Merge contiguous token spans into whole words per entity type."""
    grouped: dict[str, list[dict]] = {}
    for item in outputs:
        entity = item["entity"][2:]  # strip the B-/I- prefix
        start, end = item["start"], item["end"]
        word = text[start:end]
        spans = grouped.setdefault(entity, [])
        if spans and start == spans[-1]["end"]:
            spans[-1]["word"] += word
            spans[-1]["end"] = end
        else:
            spans.append({"word": word, "start": start, "end": end})
    return {entity: [s["word"] for s in spans] for entity, spans in grouped.items()}


def analyze(text: str) -> list[Finding]:
    outputs = _pipeline()(text)
    findings = []
    for entity, words in _group_entities(text, outputs).items():
        for word in words:
            if entity == "PASSWORD":
                findings.append(Finding(kind="password", value=word, source="Starpii"))
            else:
                findings.append(Finding(kind="pii", entity_type=entity, value=word, source="Starpii"))
    return findings


def check_status() -> AnalyzerStatus:
    token = get_settings().hf_token
    if not (isinstance(token, str) and token.startswith("hf_")):
        return AnalyzerStatus("Starpii", False, "Invalid or missing HuggingFace token")
    try:
        outputs = _pipeline()("example@gmail.com")
        ok = bool(outputs) and outputs[0]["entity"] == "I-EMAIL"
        return AnalyzerStatus("Starpii", ok, "Starpii is working" if ok else "Starpii did not detect a test email")
    except Exception as exc:
        return AnalyzerStatus("Starpii", False, str(exc))
