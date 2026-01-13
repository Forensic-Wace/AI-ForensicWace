from database import SessionLocal
from models import Text, User


def get_all_users():
    session = SessionLocal
    user = session.query(User).all()
    return user


def get_user_by_name(user_name: str):
    session = SessionLocal
    user = session.query(User).filter(User.name == user_name).all()
    return user


def get_user_by_id(id: int):
    session = SessionLocal
    user = session.query(User).filter(User.id == id).first()
    return user
