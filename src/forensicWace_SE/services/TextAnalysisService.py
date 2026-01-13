from datetime import datetime
from typing import List
import httpx

from src.forensicWace_SE.repository.database import SessionLocal
from src.forensicWace_SE.repository.models import Text


from ExtractPiiService import get_pii_from_presidio
from chatgptService import call_gpt_extract

from deepPassClient import populate_get_deep_passwords
from microsoftPIIExtractor import imageDesc, S2T, microsoft_pii_recognition
from starpii_Service import starpii_extract


def process_text(process_id: str, _id: int, timestamp, text: str, analyzers: list[str] = None):
    date_ts = datetime.fromtimestamp(timestamp / 1000)
    text = Text(msg_id=_id, process_id=process_id, text=text, user_id='1', date=date_ts)
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
                case "gpt3.5":
                    call_gpt_extract(text)
                case "microsoftPII":
                    microsoft_pii_recognition(text)
    else:
        starpii_extract(text)
        populate_get_deep_passwords(text)
        get_pii_from_presidio(text)
        call_gpt_extract(text)
    SessionLocal.commit()


def process_wadb_analysis_request(process_status, process_id, res, analyzers):
    messages_len = len(res)
    for idx, item in enumerate(res):
        # Estrai i primi sei elementi
        contact_id, _id, chat_row_id, from_me, timestamp, message_type, text_data, file_path, file_size, media_caption = item
        if message_type == 0:
            #messaggio testuale
            process_text(process_id, _id, timestamp, text_data, analyzers)
        elif message_type == 1 and 'image_OCR' in analyzers:
            #immagine
            res = imageDesc(file_path)
            new_text = res.get('caption', '') + ' ' + res.get('OCR', '')
            if media_caption:
                new_text += ' ' + media_caption
            process_text(process_id, _id, timestamp, new_text, analyzers)
        elif message_type == 2 and 'S2T' in analyzers:
            new_text = S2T(file_path)
            process_text(process_id, _id, timestamp, new_text, analyzers)
        elif message_type == 3:
            #video
            pass
        else:
            pass
        process_status[process_id]['status'] = 'Analizing'
        process_status[process_id]['details'] = f'Analized {idx + 1} over {messages_len} messages'

    process_status[process_id]['status'] = 'Finish'
    process_status[process_id]['details'] = f'Analized all messages'

    end_time = datetime.now()
    process_status[process_id]['end_time'] = end_time.isoformat()
