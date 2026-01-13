import os

from sqlalchemy_utils.models import timestamp_before_update


from datetime import datetime

from src.forensicWace_SE.globalConstants import deviceExtractions_FOLDER_ANDROID


class Messaggio:
    def __init__(self, id_messaggio, text, sent=False, sender=None, id_chat=None, timestamp=None,
                 received_timestamp=None, message_type=None, image_path=None,
                 image_caption=None, image_OCR=None, audio_path=None, audio_stt=None,
                 mime_type=None):
        """
        Inizializza un'istanza della classe Messaggio.

        :param id_messaggio: Identificativo unico del messaggio (int o str)
        :param text: Testo del messaggio (str)
        :param sent: Flag per indicare se il messaggio è stato inviato dall'utente (bool, predefinito False)
        :param id_chat: Identificativo della chat a cui appartiene il messaggio (int o str, predefinito None)
        :param timestamp: Data e ora di creazione del messaggio (datetime, predefinito None)
        :param received_timestamp: Data e ora di ricezione del messaggio (datetime, predefinito None)
        :param message_type: Tipo del messaggio, es. 'text', 'image', 'audio' (str, predefinito None)
        :param image_path: Percorso dell'immagine associata al messaggio (str, predefinito None)
        :param image_caption: Didascalia dell'immagine (str, predefinito None)
        :param image_OCR: Testo estratto dall'immagine tramite OCR (str, predefinito None)
        :param audio_path: Percorso del file audio associato al messaggio (str, predefinito None)
        :param audio_stt: Testo trascritto da un file audio (str, predefinito None)
        :param mime_type: Tipo MIME del contenuto del messaggio (str, predefinito None)

        """
        self.id_messaggio = id_messaggio
        self.text = text
        self.sent = sent
        self.sender= sender
        self.id_chat = id_chat
        self.timestamp = timestamp or datetime.utcnow()
        self.received_timestamp = received_timestamp
        self.message_type = message_type
        self.image_path = image_path
        self.image_caption = image_caption
        self.image_OCR = image_OCR
        self.audio_path = audio_path
        self.audio_stt = audio_stt
        self.mime_type = mime_type

    def __repr__(self):
        """
        Rappresentazione leggibile della classe per il debugging.
        """
        return (
            f"Messaggio("
            f"id_messaggio={self.id_messaggio!r}, text={self.text!r}, sent={self.sent!r}, "
            f"sender={self.sender!r}, id_chat={self.id_chat!r}, "
            f"timestamp={self.timestamp!r}, received_timestamp={self.received_timestamp!r}, "
            f"message_type={self.message_type!r}, image_path={self.image_path!r}, "
            f"image_caption={self.image_caption!r}, image_OCR={self.image_OCR!r}, "
            f"audio_path={self.audio_path!r}, audio_stt={self.audio_stt!r}, "
            f"mime_type={self.mime_type!r}"
            f")"
        )

    @staticmethod
    def IOS_2_MessageList(Ios_DB_Messages):
        return "MessageList"

    @staticmethod
    def Android_2_MessageList(Android_DB_Messages, extraction_path):

        """
        Converte una lista di tuple provenienti dal database Android in una lista di oggetti Messaggio.

        :param Android_DB_Messages: Lista di tuple dal database Android
        :return: Lista di oggetti Messaggio
        """
        message_list = []

        # Mapping dei tipi di messaggi
        message_type_mapping = {
            0: 'text',
            1: 'image', 42: 'image',
            2: 'audio',
            3: 'video', 43: 'video',
            13: 'gif',
            5: 'location',
            6: 'groupEvent',
            7: 'url',
            9: 'file'
        }

        for record in Android_DB_Messages:
            # Decodifica dei campi
            sender_id = record[0]  # Identificativo mittente
            id_messaggio = record[1]
            id_chat = record[2]
            inviato = bool(record[3])
            timestamp = datetime.fromtimestamp(record[4] / 1000)  # Conversione da ms a datetime
            message_type = message_type_mapping.get(record[5], 'unknown')  # Tipo di messaggio
            text = record[6]
            media_path = record[7]  # Percorso del file multimediale
            mime_type = record[10]

            # Creazione dell'oggetto Messaggio
            messaggio = Messaggio(
                id_messaggio=id_messaggio,
                text=text,
                sent=inviato,
                sender= sender_id,
                id_chat=id_chat,
                timestamp=timestamp,
                message_type=message_type,
                image_path= (os.path.normpath(os.path.join(deviceExtractions_FOLDER_ANDROID, extraction_path, media_path)
                                              ))if 'image' == message_type else None,
                audio_path = (os.path.normpath(os.path.join(deviceExtractions_FOLDER_ANDROID, extraction_path, media_path)
                    )) if mime_type and 'audio' in mime_type else None,
                mime_type=mime_type
            )

            message_list.append(messaggio)

        return message_list