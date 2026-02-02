"""
Gestione database SQLite con SQLAlchemy.
Inizializzazione, sessioni e lifecycle.
"""
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlite3

from app.config import DATABASE_URL
from app.db.models import Base

logger = logging.getLogger(__name__)

# Configurazione SQLite per robustezza (locale e Docker)
# timeout: attesa per lock (secondi) - importante per multi-thread
# check_same_thread: False per permettere accesso da thread diversi
# isolation_level: None per gestire manualmente le transazioni
connect_args = {
    "check_same_thread": False,
    "timeout": 30.0,  # Timeout per lock (30 secondi)
    "isolation_level": None,  # Autocommit mode - gestiamo manualmente
}

# Configurazioni aggiuntive per robustezza I/O
def set_sqlite_pragmas(dbapi_conn, connection_record):
    """Configura pragmas SQLite per robustezza."""
    cursor = dbapi_conn.cursor()
    # WAL mode per migliore concorrenza (consigliato per uso locale)
    # Su macOS locale, WAL è più performante e robusto
    # Su Docker/volumi montati, DELETE è più sicuro
    import os
    is_docker = os.path.exists('/.dockerenv') or os.path.exists('/proc/self/cgroup')
    if is_docker:
        cursor.execute("PRAGMA journal_mode=DELETE")  # Più sicuro per volumi montati
    else:
        cursor.execute("PRAGMA journal_mode=WAL")  # Migliore per uso locale
    # Aumenta cache per ridurre I/O
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    # Synchronous: NORMAL è un compromesso tra sicurezza e performance
    # FULL è più sicuro ma più lento, OFF è pericoloso
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Lock timeout
    cursor.execute("PRAGMA busy_timeout=30000")  # 30 secondi
    cursor.close()

# Engine con configurazione per SQLite
# StaticPool necessario per SQLite in ambiente multi-thread
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool,
    echo=False,  # True per debug SQL
    pool_pre_ping=True,  # Verifica connessioni prima di usarle
)

# Applica configurazioni SQLite
event.listen(engine, "connect", set_sqlite_pragmas)

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

