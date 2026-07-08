"""DeepPass password detection via the local REST sidecar."""

import httpx

from ...config import get_settings
from ..types import AnalyzerStatus, Finding

TIMEOUT = 30.0


def _endpoint() -> str | None:
    return get_settings().deeppass_endpoint


def analyze(text: str) -> list[Finding]:
    endpoint = _endpoint()
    if not endpoint:
        return []
    response = httpx.post(f"{endpoint}/api/text", content=text, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    model_passwords = [c["password"] for c in payload.get("model_password_candidates", [])]
    regex_passwords = [c["password"] for c in payload.get("regex_password_candidates", [])]

    findings = [Finding(kind="password", value=p, source="deeppass_model") for p in model_passwords]
    findings += [
        Finding(kind="password", value=p, source="deeppass_regex")
        for p in regex_passwords
        if p not in model_passwords
    ]
    return findings


def check_status() -> AnalyzerStatus:
    endpoint = _endpoint()
    if not endpoint:
        return AnalyzerStatus("DeepPass", False, "Endpoint not configured")
    try:
        response = httpx.post(f"{endpoint}/api/text", content="paswetr%", timeout=TIMEOUT)
        candidates = response.json().get("model_password_candidates", [])
        ok = bool(candidates) and candidates[0]["password"] == "paswetr%"
        return AnalyzerStatus("DeepPass", ok, "DeepPass is working" if ok else "Unexpected response")
    except Exception as exc:
        return AnalyzerStatus("DeepPass", False, str(exc))
