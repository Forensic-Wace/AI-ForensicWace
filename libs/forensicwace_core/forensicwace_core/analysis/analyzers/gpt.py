"""PII/password extraction through an OpenAI Assistant.

The assistant is expected to answer with a JSON object mapping entity types to
lists of values (``PASSWORD`` entries become password findings).
"""

import json
import time
from functools import lru_cache

from ...config import get_settings
from ..types import AnalyzerStatus, Finding

POLL_INTERVAL_SECONDS = 1


@lru_cache
def _client():
    from openai import OpenAI

    return OpenAI(api_key=get_settings().openai_api_key)


def _configured() -> bool:
    settings = get_settings()
    return bool(settings.use_openai_gpt and settings.openai_api_key and settings.openai_assistant_id)


def _ask_assistant(content: str) -> dict:
    client = _client()
    assistant_id = get_settings().openai_assistant_id

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(thread_id=thread.id, role="user", content=content)
    run = client.beta.threads.runs.create(assistant_id=assistant_id, thread_id=thread.id)
    while run.status != "completed":
        time.sleep(POLL_INTERVAL_SECONDS)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    response = client.beta.threads.messages.list(thread.id).data[0].content[0].text.value
    return json.loads(response)


def analyze(text: str) -> list[Finding]:
    if not _configured():
        return []
    findings = []
    for entity, words in _ask_assistant(text).items():
        if entity == "error":
            continue
        for word in words:
            if entity == "PASSWORD":
                findings.append(Finding(kind="password", value=word, source="gpt"))
            else:
                findings.append(Finding(kind="pii", entity_type=entity, value=word, source="gpt"))
    return findings


def check_status() -> AnalyzerStatus:
    if not _configured():
        return AnalyzerStatus("GPT", False, "Not enabled or not configured")
    try:
        entities = _ask_assistant("example@gmail.com")
        ok = entities.get("EMAIL_ADDRESS", [None])[0] == "example@gmail.com"
        return AnalyzerStatus("GPT", ok, "GPT is working" if ok else "Unexpected response")
    except Exception as exc:
        return AnalyzerStatus("GPT", False, str(exc))
