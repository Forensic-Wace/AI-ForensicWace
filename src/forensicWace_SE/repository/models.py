from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, DateTime, func
from sqlalchemy.orm import relationship

from src.forensicWace_SE.repository.database import Base, engine


association_table_psw = Table('text_password', Base.metadata,
                              Column("text", ForeignKey("texts.id")),
                              Column("password", ForeignKey("passwords.id")))

association_table_pii = Table('text_pii', Base.metadata,
                              Column("text", ForeignKey("texts.id")),
                              Column("PIIs", ForeignKey("PIIs.id")))


class Text(Base):
    __tablename__ = "texts"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    process_id = Column(String, nullable=False)
    msg_id = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='texts')
    text = Column(String, nullable=False)
    password = relationship('Password', secondary=association_table_psw, back_populates='text')
    pii = relationship("PII", secondary=association_table_pii, back_populates='text')
    date = Column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    address = Column(String)
    comment = Column(String)
    texts = relationship('Text', back_populates='user')


class Password(Base):
    __tablename__ = "passwords"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    password = Column(String, index=True)
    source = Column(String, nullable=False)
    text = relationship('Text', secondary=association_table_psw, back_populates='password')


class PII(Base):
    __tablename__ = "PIIs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, index=True)
    value = Column(String)
    text = relationship('Text', secondary=association_table_pii, back_populates='pii')
    source = Column(String, nullable=False)


class ProcessStatus(Base):
    __tablename__ = 'process_status'

    id = Column(Integer, primary_key=True)
    process_id = Column(String(128), nullable=False)
    OS = Column(String(50), nullable=True)
    extraction_name_udid = Column(String(255), nullable=True)
    db_path = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)
    details = Column(String)
    date_to = Column(DateTime)
    date_from = Column(DateTime)
    received = Column(Boolean, nullable=True)
    sent = Column(Boolean, nullable=True)
    contacts = Column(String)
    groups = Column(String)
    msg_type = Column(String)
    analyzers = Column(String)


if engine is not None:
    Base.metadata.create_all(engine)
