import json
import os
import time

import openai
from dotenv import load_dotenv
from openai import OpenAI

from src.forensicWace_SE import utils
from src.forensicWace_SE.repository.models import Text, PII, Password
load_dotenv()

class OpenAIClientSingleton:
    _instance = None  # Attributo di classe per memorizzare l'istanza unica

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAIClientSingleton, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Legge il file di configurazione
        configIniFile = utils.ReadConfigFile()
        # Crea un'istanza del client OpenAI
        self.client = OpenAI(api_key=configIniFile['API']['openaiapikey'])
        # Recupera l'Assistant ID
        self.assistant_id_extract = configIniFile['API']['gtpassistantidextract']
        # Recupera l'assistente esistente
        self.my_assistant_extract = self.client.beta.assistants.retrieve(
            self.assistant_id_extract
        )

def check_status():

    configIniFile = utils.ReadConfigFile()
    api_key = configIniFile['API']['openaiapikey']
    assistant_id_extract = configIniFile['API']['gtpassistantidextract']
    if isinstance(api_key, str):
        print("Valid OpenAI token")
        if isinstance(assistant_id_extract, str):
            print("Valid OpenAI assistant token")

            try:
                client = OpenAIClientSingleton().client
                # Crea una conversazione (Thread)
                thread = client.beta.threads.create()

                message = client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content="example@gmail.com"
                )

                # Esegui l'Assistant per generare una risposta
                run = client.beta.threads.runs.create(assistant_id=OpenAIClientSingleton().assistant_id_extract, thread_id=thread.id)
                # # Estrai la risposta dal risultato
                while run.status != 'completed':
                    run = client.beta.threads.runs.retrieve(
                        thread_id=thread.id,
                        run_id=run.id
                    )
                    print(run.status)
                    time.sleep(1)

                response = client.beta.threads.messages.list(thread.id).data[0].content[0].text.value
                # Dividi la stringa in righe separate
                entities = json.loads(response)
                if(entities['EMAIL_ADDRESS'][0] == 'example@gmail.com'):
                    return True, "GPT", "GPT is working"
                else:
                    return False, "GPT", "GPT not working"
            except Exception as ex:
                print(ex)
                return False, "GPT", ex

        else:
            print("Unvalid OpenAI assistant token")
            return False, "GPT", "OpenAI assistant token"

    else:
        print("Unvalid OpenAI Token")
        return False, "GPT", "OpenAI Token"


def call_gpt_extract(text: Text):
    client=OpenAIClientSingleton
    # Crea una conversazione (Thread)
    thread = client.beta.threads.create()

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=text.text
    )

    # Esegui l'Assistant per generare una risposta
    run  = client.beta.threads.runs.create(assistant_id=client.assistant_id_extract, thread_id=thread.id)
    # # Estrai la risposta dal risultato
    while run.status != 'completed':
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        print(run.status)
        time.sleep(1)

    response = client.beta.threads.messages.list(thread.id).data[0].content[0].text.value
    # Dividi la stringa in righe separate
    entities = json.loads(response)

    # Stampa le entità estratte
    for entity, words in entities.items():
        for word in words:
            print(f"{entity}: {word}")

            if entity == 'PASSWORD':
                psw = Password(password=word, source='gpt')
                text.password.append(psw)
            elif entity == 'error':
                continue
            else:
                pii = PII(type=entity, value=word, source='gpt')
                text.pii.append(pii)

    return entities

def create_combined_json(input_string1, input_string2):
    # Rimuovi le parentesi graffe dalle stringhe di input
    stripped1 = input_string1.replace('{', '').replace('}', '').replace('\n', '')
    stripped2 = input_string2.replace('{', '').replace('}', '')

    # Combina le stringhe con una virgola
    combined = '{' + stripped1 + ',' + stripped2 + '}'

    return combined

