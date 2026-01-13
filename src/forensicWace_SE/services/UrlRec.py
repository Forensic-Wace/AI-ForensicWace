import re
from typing import List

from presidio_analyzer import RecognizerResult, EntityRecognizer
from presidio_analyzer.nlp_engine import NlpArtifacts


class NewURLRecognizer(EntityRecognizer):
    expected_confidence_level = 0.7  # expected confidence level for this recognizer

    def load(self) -> None:
        """No loading is required."""
        pass

    def analyze(
            self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts
    ) -> List[RecognizerResult]:
        """
        Analyzes test to find tokens which represent numbers (either 123 or One Two Three).
        """
        results = []

        # iterate over the spaCy tokens, and call `token.like_url`
        for token in nlp_artifacts.tokens:
            if token.like_url and not self.isIp(token.text):
                result = RecognizerResult(
                    entity_type="URL_NEW",
                    start=token.idx,
                    end=token.idx + len(token),
                    score=self.expected_confidence_level,
                )
                results.append(result)
        return results

    def isIp(self, text):
        pattern = re.compile('((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}')
        if pattern.match(text) == None:
            return False
        else:
            return True
