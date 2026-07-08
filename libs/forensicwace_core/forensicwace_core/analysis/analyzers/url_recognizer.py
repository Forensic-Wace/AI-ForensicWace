"""Custom Presidio recognizer flagging URL-like tokens (excluding bare IPs)."""

import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

_IP_PATTERN = re.compile(r"((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}")


class UrlRecognizer(EntityRecognizer):
    CONFIDENCE = 0.7

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts) -> List[RecognizerResult]:
        results = []
        for token in nlp_artifacts.tokens:
            if token.like_url and not _IP_PATTERN.match(token.text):
                results.append(
                    RecognizerResult(
                        entity_type="URL_NEW",
                        start=token.idx,
                        end=token.idx + len(token),
                        score=self.CONFIDENCE,
                    )
                )
        return results
