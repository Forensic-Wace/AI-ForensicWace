from datetime import datetime

from src.forensicWace_SE.repository.database import SessionLocal
from src.forensicWace_SE.repository.models import Text, User, association_table_pii, PII


def get_all_texts():
    session = SessionLocal
    texts = session.query(Text).all()
    return texts



# Function to get text entries by datetime range
def get_texts_by_datetime_range(start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    texts = session.query(Text).filter(Text.date >= start_datetime, Text.date <= end_datetime).all()
    return texts


def get_texts_by_user_id_datetime_range(user_id: int, start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    texts = session.query(Text).filter(Text.user_id == user_id, Text.date >= start_datetime,
                                       Text.date <= end_datetime).all()
    return texts


def get_texts_by_user_id(user_id: int):
    session = SessionLocal
    texts = session.query(Text).filter(Text.user_id == user_id).all()
    return texts

def get_texts_by_process_id(process_id: str):
    session = SessionLocal
    texts = session.query(Text).filter(Text.process_id == process_id).all()
    return texts

def get_texts_by_user_id_full(user_id: int):
    session = SessionLocal
    texts = session.query(Text).filter(Text.user_id == user_id).all()
    results = []

    for text in texts:
        text_info = {
            'id': text.id,
            'text': text.text,
            'date': text.date,
            'passwords': [{'id': p.id, 'password': p.password, 'source': p.source} for p in text.password],
            'piis': [{'id': p.id, 'type': p.type, 'value': p.value, 'source': p.source} for p in text.pii]
        }
        results.append(text_info)

    return results

def get_texts_by_user_name(user_name: str):
    session = SessionLocal()
    texts = session.query(Text).join(User).filter(User.name == user_name).all()
    return texts
