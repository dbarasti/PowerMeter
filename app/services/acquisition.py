"""
Servizio di acquisizione dati Modbus.
Gestisce lettura periodica dai due SDM120 e salvataggio su database.
Thread-safe, gestisce errori e retry.
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.modbus.sdm120 import SDM120Reader
from app.config import MODBUS_CONFIG, ACQUISITION_CONFIG
from app.db.models import Measurement, TestSession, SessionStatus, DeviceType

logger = logging.getLogger(__name__)


class AcquisitionService:
    """
    Servizio per acquisizione dati da Modbus.
    Esegue letture periodiche e salva su database.
    Thread-safe: un solo thread legge Modbus alla volta.
    """
    
    def __init__(self, db: Session):
        """
        Inizializza il servizio di acquisizione.
        
        Args:
            db: Sessione database SQLAlchemy
        """
        self.db = db
        self.reader: Optional[SDM120Reader] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._current_session_id: Optional[int] = None
        self._sample_rate = ACQUISITION_CONFIG["default_sample_rate"]
    
    def start(self, session_id: int, sample_rate_seconds: int = 5):
        """
        Avvia l'acquisizione per una sessione di test.
        
        Args:
            session_id: ID della TestSession
            sample_rate_seconds: Frequenza di campionamento in secondi
            
        Returns:
            Tuple (success, error_message)
        """
        with self._lock:
            if self._running:
                error_msg = "Acquisizione già in esecuzione per un'altra sessione"
                logger.warning(error_msg)
                return False, error_msg
            
            # Verifica che la sessione esista e sia in stato IDLE
            session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
            if not session:
                error_msg = f"Sessione {session_id} non trovata"
                logger.error(error_msg)
                return False, error_msg
            
            if session.status != SessionStatus.IDLE.value:
                error_msg = f"La sessione non può essere avviata: stato attuale '{session.status}' (deve essere IDLE)"
                logger.error(error_msg)
                return False, error_msg
            
            # Connetti Modbus se non già connesso
            if not self.reader or not self.reader.is_connected():
                self.reader = SDM120Reader(
                    port=MODBUS_CONFIG["port"],
                    baudrate=MODBUS_CONFIG["baudrate"],
                    timeout=MODBUS_CONFIG["timeout"]
                )
                if not self.reader.connect():
                    error_msg = (
                        f"Impossibile connettersi al dispositivo Modbus sulla porta {MODBUS_CONFIG['port']}. "
                        f"Verifica che:\n"
                        f"- Il dispositivo sia collegato via USB-RS485\n"
                        f"- La porta seriale sia corretta (configurata: {MODBUS_CONFIG['port']})\n"
                        f"- Il driver USB-RS485 sia installato\n"
                        f"- Nessun altro programma stia usando la porta seriale"
                    )
                    logger.warning(error_msg)
                    return False, error_msg
            
            # Aggiorna stato sessione
            session.status = SessionStatus.RUNNING.value
            session.started_at = datetime.utcnow()
            self.db.commit()
            
            # Avvia thread acquisizione
            self._current_session_id = session_id
            self._sample_rate = sample_rate_seconds
            self._running = True
            self._thread = threading.Thread(target=self._acquisition_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"Acquisizione avviata per sessione {session_id} (sample rate: {sample_rate_seconds}s)")
            return True, ""
    
    def stop(self):
        """
        Ferma l'acquisizione e aggiorna lo stato della sessione.
        """
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Attendi che il thread finisca (max 2 secondi)
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            
            # Aggiorna stato sessione
            if self._current_session_id:
                session = self.db.query(TestSession).filter(
                    TestSession.id == self._current_session_id
                ).first()
                if session:
                    session.status = SessionStatus.COMPLETED.value
                    session.completed_at = datetime.utcnow()
                    self.db.commit()
                    logger.info(f"Sessione {self._current_session_id} completata")
            
            self._current_session_id = None
    
    def is_running(self) -> bool:
        """Verifica se l'acquisizione è in esecuzione."""
        with self._lock:
            return self._running
    
    def get_current_session_id(self) -> Optional[int]:
        """Restituisce l'ID della sessione corrente, se attiva."""
        with self._lock:
            return self._current_session_id
    
    def _acquisition_loop(self):
        """
        Loop principale di acquisizione dati.
        Esegue letture periodiche dai due SDM120 e salva su database.
        """
        logger.info("Thread acquisizione avviato")
        
        while self._running:
            try:
                # Leggi da entrambi i dispositivi
                heater_data = self.reader.read_all(MODBUS_CONFIG["slave_ids"]["heater"])
                fan_data = self.reader.read_all(MODBUS_CONFIG["slave_ids"]["fan"])
                
                # Salva misure su database
                if heater_data:
                    self._save_measurement(
                        self._current_session_id,
                        DeviceType.HEATER.value,
                        heater_data["power_w"],
                        heater_data["energy_kwh"]
                    )
                
                if fan_data:
                    self._save_measurement(
                        self._current_session_id,
                        DeviceType.FAN.value,
                        fan_data["power_w"],
                        fan_data["energy_kwh"]
                    )
                
                # Attendi prima della prossima lettura
                time.sleep(self._sample_rate)
                
            except Exception as e:
                logger.error(f"Errore nel loop di acquisizione: {e}")
                # Continua anche in caso di errore (non bloccare il loop)
                time.sleep(self._sample_rate)
        
        logger.info("Thread acquisizione terminato")
    
    def _save_measurement(self, session_id: int, device_type: str, power_w: float, energy_kwh: float):
        """
        Salva una misura su database.
        
        Args:
            session_id: ID sessione
            device_type: "heater" o "fan"
            power_w: Potenza in Watt
            energy_kwh: Energia in kWh
        """
        try:
            measurement = Measurement(
                session_id=session_id,
                device_type=device_type,
                power_w=power_w,
                energy_kwh=energy_kwh,
                timestamp=datetime.utcnow()
            )
            self.db.add(measurement)
            self.db.commit()
        except Exception as e:
            logger.error(f"Errore salvataggio misura: {e}")
            self.db.rollback()
    
    def shutdown(self):
        """
        Chiude il servizio e disconnette Modbus.
        Chiamare all'uscita dell'applicazione.
        """
        self.stop()
        if self.reader:
            self.reader.disconnect()
        logger.info("AcquisitionService chiuso")

