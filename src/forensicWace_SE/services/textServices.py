from datetime import datetime
from src.forensicWace_SE.repository.database import SessionLocal
from src.forensicWace_SE.repository.models import Text
from src.forensicWace_SE.services.ExtractPiiService import get_pii_from_presidio
from src.forensicWace_SE.services.chatgptService import call_gpt_extract

from src.forensicWace_SE.services.deepPassClient import populate_get_deep_passwords
from src.forensicWace_SE.services.microsoftPIIExtractor import  microsoft_pii_recognition
from src.forensicWace_SE.services.starpii_Service import starpii_extract


def process_text(message,process_id: str, analyzers: list[str] = None):
    date_ts = message.timestamp
    #user_id=1 for future development of multi users feature
    text = Text(msg_id=message.id_messaggio , process_id=process_id, text=message.text, user_id='1', date=date_ts)
    SessionLocal.add(text)
    if analyzers:
        for analyzer in analyzers:
            match analyzer:
                case "starpii":
                    starpii_extract(text)
                case "deep_password":
                    populate_get_deep_passwords(text)
                case "presidio":
                     get_pii_from_presidio(text)
                case "gpt":
                    call_gpt_extract(text)
                case "microsoftPII":
                   microsoft_pii_recognition(text)

    SessionLocal.commit()