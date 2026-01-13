import re
from azure.core.credentials import AzureKeyCredential

from src.forensicWace_SE import utils
from src.forensicWace_SE.repository.models  import Text, PII
configIniFile = utils.ReadConfigFile()

key = configIniFile['API']['mspiikey']
endpoint = configIniFile['API']['mspiiendpoint']

from azure.ai.textanalytics import TextAnalyticsClient


class ClientSingleton:
    _instance = None  # Attributo per memorizzare l'istanza unica

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ClientSingleton, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Autenticazione e creazione del client
        self.ta_credential = AzureKeyCredential(key)
        self.client = TextAnalyticsClient(endpoint=endpoint, credential=self.ta_credential)


def check_status():
    if isinstance(key, str):
        print("Valid Azure token")
        if isinstance(endpoint, str):
            pattern = re.compile(
                r"^(https?://)"  # Deve iniziare con http:// o https://
                r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"  # Dominio
                r"(:\d+)?(/.*)?$"  # Porta opzionale e percorso
            )
            if bool(pattern.match(endpoint)):
                print("Valid endpoint")
                try:
                    clientSingleton = ClientSingleton()
                    response = clientSingleton.client.recognize_pii_entities(["example@email.com"], language="en")

                    service_running = response[0].entities[0].category.lower() == 'email'

                    if  service_running:
                        return True, "MS PII", "Microsoft PII is working"
                    else:
                        return False, "MS PII", "Microsoft PII is not working"
                except Exception as e:
                    print(e)
                    return False, "MS PII", e
            else:
                return False, "MS PII", "Unvalid Azure endpoint"
        else:
            print("Unvalid Azure token")
            return False, "MS PII", "Unvalid Azure  token"
    else:
        print("Unvalid Azure Token")
        return False,"Unvalid Azure Token"

# Example method for detecting sensitive information (PII) from text
def microsoft_pii_recognition(text: Text):

    response = ClientSingleton.client.recognize_pii_entities([text.text], language="en")
    result = [doc for doc in response if not doc.is_error]
    for doc in result:
        print("Redacted Text: {}".format(doc.redacted_text))
        for entity in doc.entities:
            pii = PII(type=entity.category, value=entity.text,
                      source='microsoftPII')
            text.pii.append(pii)
            print("Entity: {}".format(entity.text))
            print("	Category: {}".format(entity.category))
            print("	Confidence Score: {}".format(entity.confidence_score))
            print("	Offset: {}".format(entity.offset))
            print("	Length: {}".format(entity.length))
