"""ORM models for analysis results.

Table and column names are kept identical to the legacy schema so existing
databases remain usable without migration.
"""

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint
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
    """Operator accounts and legacy analysis subjects.

    Rows with ``username`` set are login-capable platform users; legacy rows
    without it (pre-auth analysis subjects) are kept untouched.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    address = Column(String)
    comment = Column(String)

    # Authentication (nullable: legacy subject rows never log in)
    username = Column(String(64), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(10))  # admin | analyst
    is_active = Column(Boolean)
    token_version = Column(Integer)  # bumped to revoke outstanding sessions
    created_at = Column(DateTime(timezone=True))
    last_login = Column(DateTime(timezone=True))

    texts = relationship("Text", back_populates="user")


class Password(Base):
    __tablename__ = "passwords"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    password = Column(String, index=True)
    source = Column(String, nullable=False)
    # Provenance: exact analyzer build that produced the finding (chain of custody)
    analyzer_version = Column(String(50))
    analyzer_digest = Column(String(120))

    texts = relationship("Text", secondary=text_password, back_populates="passwords")


class PII(Base):
    __tablename__ = "PIIs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, index=True)
    value = Column(String)
    source = Column(String, nullable=False)
    analyzer_version = Column(String(50))
    analyzer_digest = Column(String(120))

    texts = relationship("Text", secondary=text_pii, back_populates="piis")


class Project(Base):
    """A case folder: groups backups uploaded through the web UI."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String, default="")
    created_at = Column(DateTime(timezone=True))
    created_by = Column(Integer)  # users.id of the operator

    backups = relationship("ProjectBackup", back_populates="project", cascade="all, delete-orphan")


class ProjectBackup(Base):
    """A backup uploaded into a project and mirrored to object storage.

    ``status`` lifecycle: processing -> hydrating -> stored | error.
    (platform, identifier) is globally unique because hydration materializes
    the backup into the shared local extraction roots.
    """

    __tablename__ = "project_backups"
    __table_args__ = (UniqueConstraint("platform", "identifier", name="uq_project_backups_identity"),)

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    platform = Column(String(10), nullable=False)
    identifier = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False)
    detail = Column(String, default="")
    object_prefix = Column(String, nullable=False)
    original_filename = Column(String(255))
    size_bytes = Column(BigInteger, default=0)
    file_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_by = Column(Integer)

    project = relationship("Project", back_populates="backups")


class Analyzer(Base):
    """An installed analyzer (marketplace phase A: dynamic registry).

    ``builtin`` rows point at adapters shipped in the core library and are
    (re)seeded at API startup; ``http`` rows are containers implementing the
    fw-analyzer/1 contract, registered at runtime.
    """

    __tablename__ = "analyzers"

    key = Column(String(64), primary_key=True)
    name = Column(String(200), nullable=False)
    version = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False)  # builtin | http
    capabilities = Column(JSON, nullable=False)  # list[str], see contract.Capability
    input = Column(String(10), nullable=False)  # text | audio | image
    trust = Column(String(10), nullable=False, default="local")  # local | cloud
    endpoint = Column(String)  # http type only
    image = Column(String)
    image_digest = Column(String(120))
    config = Column(JSON, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    installed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class AuditLog(Base):
    """Append-only operator action trail (chain of custody).

    ``username`` is denormalized on purpose: the entry must stay legible even
    if the account is later renamed or removed.
    """

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), nullable=False, index=True)
    user_id = Column(Integer)
    username = Column(String(64))
    action = Column(String(50), nullable=False, index=True)
    resource = Column(String(255))
    detail = Column(String)


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
    created_by = Column(Integer)  # users.id of the submitting operator
