from datetime import datetime

from database import SessionLocal
from models import Text, User, PII, association_table_pii, Password, association_table_psw


def get_all_psw():
    session = SessionLocal
    texts = session.query(Password).all()
    return texts


# Function to get text entries by datetime range
def get_psw_by_params(source, start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    query = session.query(Password).join(association_table_psw).join(Text)

    # Apply filters based on the provided parameters
    if source:
        query = query.filter(Password.source == source)
    if start_datetime:
        query = query.filter(Text.date >= start_datetime)
    if end_datetime:
        query = query.filter(Text.date <= end_datetime)

    # Execute the query and return the results
    texts = query.all()
    return texts



def get_psw_by_user_id_and_params(user_id: int, source, start_datetime: datetime, end_datetime: datetime):
    session = SessionLocal
    query = session.query(Password).join(association_table_psw).join(Text)

    # Apply filters based on the provided parameters
    query = query.filter(Text.user_id == user_id)
    if source:
        query = query.filter(Password.source == source)
    if start_datetime:
        query = query.filter(Text.date >= start_datetime)
    if end_datetime:
        query = query.filter(Text.date <= end_datetime)

    # Execute the query and return the results
    texts = query.all()
    return texts


def get_psw_by_user_id(user_id: int):
    session = SessionLocal
    texts = session.query(Password).join(association_table_psw).join(Text).filter(Text.user_id == user_id).all()
    return texts
