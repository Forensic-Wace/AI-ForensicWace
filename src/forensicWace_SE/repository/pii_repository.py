from datetime import datetime

from database import SessionLocal
from models import Text, User, PII, association_table_pii


def get_all_pii():
    session = SessionLocal
    texts = session.query(PII).all()
    return texts


# Function to get text entries by datetime range
def get_pii_by_params(pii_type, source, start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    query = session.query(PII).join(association_table_pii).join(Text)

    # Apply filters based on the provided parameters
    if pii_type:
        query = query.filter(PII.type == pii_type)
    if source:
        query = query.filter(PII.source == source)
    if start_datetime:
        query = query.filter(Text.date >= start_datetime)
    if end_datetime:
        query = query.filter(Text.date <= end_datetime)

    # Execute the query and return the results
    texts = query.all()
    return texts



def get_pii_by_user_id_and_params(user_id: int, pii_type, source, start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    query = session.query(PII).join(association_table_pii).join(Text)

    # Apply filters based on the provided parameters
    query = query.filter(Text.user_id == user_id)
    if pii_type:
        query = query.filter(PII.type == pii_type)
    if source:
        query = query.filter(PII.source == source)
    if start_datetime:
        query = query.filter(Text.date >= start_datetime)
    if end_datetime:
        query = query.filter(Text.date <= end_datetime)

    # Execute the query and return the results
    texts = query.all()
    return texts


def get_pii_by_user_id(user_id: int):
    session = SessionLocal
    texts = session.query(PII).join(association_table_pii).join(Text).filter(Text.user_id == user_id).all()
    return texts
