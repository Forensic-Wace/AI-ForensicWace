from transformers import pipeline

from src.forensicWace_SE import utils
from src.forensicWace_SE.repository.models import Text, PII, Password

configIniFile = utils.ReadConfigFile()

def check_status():
    token = configIniFile['API']['hftoken']
    if isinstance(token, str) and token.startswith("hf_"):
        print("Valid hugging face token")
        try:
            pipe = pipeline("token-classification", model="bigcode/starpii", token=configIniFile['API']['hftoken'])
            outputs = pipe('example@gmail.com')
            if outputs:
                if (pipe('example@gmail.com')[0]['entity'] == 'I-EMAIL'):
                    return True, "Starpii", "Starpii is working"
            else:
                return False, "Starpii", "Starpii not working"
        except Exception as ex:
            print(ex)
            return False, "Starpii", ex
    else:
        print("Unvalid Token")
        return False, "Starpii", "Unvalid hftoken"


def starpii_extract(text: Text):
    # Use a pipeline as a high-level helper

    pipe = pipeline("token-classification", model="bigcode/starpii", token=configIniFile['API']['hftoken'])
    original_text = text.text
    outputs = pipe(text.text)

    # Crea un dizionario vuoto per memorizzare le entità
    entities = {}

    # Itera attraverso ogni elemento nella lista
    for item in outputs:
        # Estrai l'entità e gli indici di inizio e fine
        entity = item['entity']
        start = item['start']
        end = item['end']

        # Rimuovi il prefisso "B-" o "I-" dall'entità
        entity = entity[2:]

        # Estrai la parola dal testo originale
        word = original_text[start:end]

        # Se l'entità non è già nel dizionario, aggiungila
        if entity not in entities:
            entities[entity] = [{'word': word, 'start': start, 'end': end}]
        else:
            # Se l'indice di inizio della parola corrente è uguale all'indice di fine dell'ultima parola,
            # allora le parole sono contigue e dovrebbero essere raggruppate insieme
            if start == entities[entity][-1]['end']:
                entities[entity][-1]['word'] += word
                entities[entity][-1]['end'] = end
            else:
                # Altrimenti, le parole non sono contigue e dovrebbero essere separate
                entities[entity].append({'word': word, 'start': start, 'end': end})

        # Stampa le entità estratte
    for entity, words in entities.items():
        for word in words:
            print(f"{entity}: {word['word']}")
            if entity != 'PASSWORD':
                pii = PII(type=entity, value=word['word'], source='Starpii')
                text.pii.append(pii)
            else:
                psw = Password(password=word['word'], source='Starpii')
                text.password.append(psw)
    return entities

