from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.exc import OperationalError
from sqlalchemy_utils import database_exists, create_database
from src.forensicWace_SE import utils

load_dotenv()

configIniFile = utils.ReadConfigFile()

SQLALCHEMY_DATABASE_URL = configIniFile['API'].get('databaseurl')

engine = None
SessionLocal = None

if SQLALCHEMY_DATABASE_URL:
    try:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_pre_ping=True,   # utile se il DB si disconnette
            future=True
        )

        # Qui non serve connettersi subito → la connessione sarà lazy
        if not database_exists(engine.url):
            create_database(engine.url)

        SessionLocal = Session(autocommit=False, autoflush=False, bind=engine)

    except OperationalError as e:
        print(f"[WARNING] Connessione al database fallita: {e}")
        # fallback senza DB
        engine = None
        SessionLocal = None
else:
    print("[WARNING] Nessun DATABASE_URL configurato!")

Base = declarative_base()