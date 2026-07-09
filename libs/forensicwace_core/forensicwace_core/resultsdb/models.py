"""ORM models for analysis results.

Table and column names are kept identical to the legacy schema so existing
databases remain usable without migration.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from .engine import Base

text_password = Table(
    "text_password",
    Base.metadata,
    Column("text", ForeignKey("texts.id")),
    Column("password", ForeignKey("passwords.id")),
)

text_pii = Table(
    "text_pii",
    Base.metadata,
    Column("text", ForeignKey("texts.id")),
    Column("PIIs", ForeignKey("PIIs.id")),
)


class Text(Base):
    __tablename__ = "texts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    process_id = Column(String, nullable=False, index=True)
    msg_id = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(String, nullable=False)
    date = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="texts")
    passwords = relationship("Password", secondary=text_password, back_populates="texts")
    piis = relationship("PII", secondary=text_pii, back_populates="texts")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    address = Column(String)
    comment = Column(String)

    texts = relationship("Text", back_populates="user")


class Password(Base):
    __tablename__ = "passwords"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    password = Column(String, index=True)
    source = Column(String, nullable=False)

    texts = relationship("Text", secondary=text_password, back_populates="passwords")


class PII(Base):
    __tablename__ = "PIIs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, index=True)
    value = Column(String)
    source = Column(String, nullable=False)

    texts = relationship("Text", secondary=text_pii, back_populates="piis")


class ProcessStatus(Base):
    __tablename__ = "process_status"

    id = Column(Integer, primary_key=True)
    process_id = Column(String(128), nullable=False, unique=True, index=True)
    OS = Column(String(50))
    extraction_name_udid = Column(String(255))
    db_path = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String(50))
    details = Column(String)
    date_to = Column(DateTime)
    date_from = Column(DateTime)
    received = Column(Boolean)
    sent = Column(Boolean)
    contacts = Column(String)
    groups = Column(String)
    msg_type = Column(String)
    analyzers = Column(String)
    total_messages = Column(Integer, default=0)
    analyzed_messages = Column(Integer, default=0)
    failed_messages = Column(Integer, default=0)
