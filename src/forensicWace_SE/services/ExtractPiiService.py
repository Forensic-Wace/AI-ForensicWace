from presidio_analyzer import AnalyzerEngine
from  src.forensicWace_SE.services.UrlRec import NewURLRecognizer

from src.forensicWace_SE.repository.models import Text, PII
new_url_recognizer = NewURLRecognizer(supported_entities=["URL_NEW"])

analyzer = AnalyzerEngine()
analyzer.registry.add_recognizers_from_yaml('src/forensicWace_SE/presidio_recognizers/recognizers.yaml')
analyzer.registry.add_recognizer(new_url_recognizer)
model_threshold = 0.5

def check_status():
    try:

        piis = analyzer.analyze(text="IT60X0542811101000000123456", entities=["IBAN_CODE"],  language="en", score_threshold=model_threshold)

        if(piis[0].entity_type == 'IBAN_CODE'):
            return True, "Presidio", "Presidio Recognizer is working"
        else:
            return False, "Presidio", "Presidio Recognizer not working"

    except Exception as ex:
        print(ex)
        return False, "Presidio", ex

def get_pii_from_presidio(text: Text):
    piis = analyzer.analyze(text=text.text, language="en", score_threshold=model_threshold)
    for pii_estracted in piis:
        pii = PII(type=pii_estracted.entity_type, value=text.text[pii_estracted.start:pii_estracted.end], source='presidio')
        text.pii.append(pii)
    return piis
