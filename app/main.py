"""
Main application entry point.
FastAPI backend API per Thermal Test System.
Il frontend Svelte è nella cartella frontend/.
"""
import logging
import sys
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.config import SERVER_CONFIG, AUTH_CONFIG
from app.db.database import init_db, get_db
from app.db.models import User
from app.services.acquisition import AcquisitionService
from app.api import auth, sessions, data
from passlib.context import CryptContext

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('thermal_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Global acquisition service
acquisition_service: AcquisitionService = None


def create_default_user(db: Session):
    """Crea utente admin di default se non esiste."""
    user = db.query(User).filter(User.username == AUTH_CONFIG["default_username"]).first()
    if not user:
        hashed_password = pwd_context.hash(AUTH_CONFIG["default_password"])
        user = User(
            username=AUTH_CONFIG["default_username"],
            hashed_password=hashed_password,
            is_active=True
        )
        db.add(user)
        db.commit()
        logger.info(f"Utente default creato: {AUTH_CONFIG['default_username']}")
        logger.warning(f"PASSWORD DEFAULT: {AUTH_CONFIG['default_password']} - CAMBIARE IN PRODUZIONE!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: startup e shutdown.
    Inizializza database, crea utente default, avvia servizio acquisizione.
    """
    # Startup
    logger.info("=== Avvio Thermal Test System ===")
    
    # Inizializza database
    init_db()
    logger.info("Database inizializzato")
    
    # Crea utente default
    db = next(get_db())
    try:
        create_default_user(db)
    finally:
        db.close()
    
    # Inizializza servizio acquisizione (non avviato, solo inizializzato)
    global acquisition_service
    from app.db.database import SessionLocal
    db_session = next(get_db())
    acquisition_service = AcquisitionService(db_session)
    # Salva factory per ricreare sessioni in caso di errore I/O
    acquisition_service._db_factory = SessionLocal
    sessions.set_acquisition_service(acquisition_service)
    logger.info("Servizio acquisizione inizializzato")
    
    yield
    
    # Shutdown
    logger.info("=== Chiusura Thermal Test System ===")
    if acquisition_service:
        acquisition_service.shutdown()
    logger.info("Applicazione chiusa")


# FastAPI app
app = FastAPI(
    title="Thermal Test System",
    description="Sistema di test termici per camion frigoriferi",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers API
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(data.router)


if __name__ == "__main__":
    import uvicorn
    
    # Avvia server
    url = f"http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}"
    logger.info(f"Server in avvio su {url}")
    
    # Apri browser se richiesto
    if SERVER_CONFIG.get("auto_open_browser", False):
        def open_browser():
            import time
            time.sleep(1.5)  # Attendi che il server sia pronto
            webbrowser.open(url)
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run(
        "app.main:app",
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        reload=SERVER_CONFIG["reload"],
        log_level="info"
    )

