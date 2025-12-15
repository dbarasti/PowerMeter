"""
Gestione database SQLite con SQLAlchemy.
Inizializzazione, sessioni e lifecycle.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import DATABASE_URL
from app.db.models import Base

# Engine con configurazione per SQLite
# StaticPool necessario per SQLite in ambiente multi-thread
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,  # True per debug SQL
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Inizializza il database creando tutte le tabelle.
    Chiamare all'avvio dell'applicazione.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency injection per FastAPI.
    Fornisce una sessione database che viene chiusa automaticamente.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

