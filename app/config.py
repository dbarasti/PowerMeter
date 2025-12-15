"""
Configurazione applicazione per test termici camion frigoriferi.
Gestisce parametri Modbus, database, autenticazione e server.
"""
import os
from pathlib import Path

# Path base dell'applicazione
BASE_DIR = Path(__file__).parent.parent
APP_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database SQLite
DATABASE_URL = f"sqlite:///{DATA_DIR}/thermal_tests.db"

# Configurazione Modbus RTU
MODBUS_CONFIG = {
    "port": os.getenv("MODBUS_PORT", "/dev/cu.usbserial-BG01Q45C"),  # Windows: COM3, Linux: /dev/ttyUSB0
    "baudrate": 9600,
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1,
    "timeout": 1.0,  # secondi
    "slave_ids": {
        "heater": 1,  # SDM120 stufa
        "fan": 2,     # SDM120 ventilatore
    }
}

# Configurazione acquisizione dati
ACQUISITION_CONFIG = {
    "default_sample_rate": 5,  # secondi tra una lettura e l'altra
    "max_retries": 3,
    "retry_delay": 0.5,  # secondi
}

# Configurazione autenticazione
AUTH_CONFIG = {
    "secret_key": os.getenv("SECRET_KEY", "change-this-secret-key-in-production"),
    "algorithm": "HS256",
    "access_token_expire_minutes": 480,  # 8 ore
    "default_username": "admin",
    "default_password": "admin",  # DA CAMBIARE AL PRIMO AVVIO
}

# Configurazione server
SERVER_CONFIG = {
    "host": "0.0.0.0",  # Accetta connessioni da LAN
    "port": 8000,
    "reload": False,  # False in produzione
    "auto_open_browser": False,  # Disabilita apertura automatica browser
}

# Configurazione web UI
WEB_CONFIG = {
    "title": "Thermal Test System",
    "refresh_interval": 2000,  # ms per aggiornamento live
}

