"""
Servizio di acquisizione dati Modbus.
Gestisce lettura periodica dai due RS-PRO e salvataggio su database.
Thread-safe, gestisce errori e retry.
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.modbus.rspro import RSProReader
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
        self.reader: Optional[RSProReader] = None
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
                self.reader = RSProReader(
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
        Esegue letture periodiche dai due RS-PRO e salva su database.
        Gestisce automaticamente disconnessioni e riconnessioni USB.
        Ferma automaticamente la sessione quando viene raggiunta la durata prevista.
        """
        logger.info("Thread acquisizione avviato")
        consecutive_errors = 0
        max_consecutive_errors = 10  # Dopo 10 errori consecutivi, tenta riconnessione (aumentato per daisy chain)
        
        while self._running:
            try:
                # Verifica se la durata della sessione è stata raggiunta
                if self._current_session_id:
                    session = self.db.query(TestSession).filter(
                        TestSession.id == self._current_session_id
                    ).first()
                    
                    if session and session.duration_minutes and session.started_at:
                        # Calcola tempo trascorso
                        elapsed = datetime.utcnow() - session.started_at
                        elapsed_minutes = elapsed.total_seconds() / 60.0
                        
                        # Se la durata è stata raggiunta, ferma la sessione
                        if elapsed_minutes >= session.duration_minutes:
                            logger.info(
                                f"Sessione {self._current_session_id} completata: "
                                f"durata raggiunta ({elapsed_minutes:.1f}/{session.duration_minutes} minuti)"
                            )
                            # Aggiorna stato sessione direttamente (non chiamare stop() per evitare join del thread corrente)
                            session.status = SessionStatus.COMPLETED.value
                            session.completed_at = datetime.utcnow()
                            self.db.commit()
                            logger.info(f"Sessione {self._current_session_id} completata e aggiornata")
                            
                            # Ferma il loop
                            with self._lock:
                                self._running = False
                                self._current_session_id = None
                            return
                
                # Verifica connessione prima di ogni lettura
                if not self.reader or not self.reader.is_connected():
                    logger.warning("Connessione Modbus persa, tentativo di riconnessione...")
                    if not self._reconnect():
                        logger.warning("Riconnessione fallita, attendo prima di riprovare...")
                        time.sleep(self._sample_rate * 2)  # Attendi più a lungo se non connesso
                        consecutive_errors += 1
                        continue
                    else:
                        logger.info("Riconnessione Modbus riuscita")
                        consecutive_errors = 0
                
                # Leggi da entrambe le fasi del dispositivo RS-PRO
                # Fase 1 = Stufa (Heater), Fase 2 = Ventilatore (Fan)
                slave_id = MODBUS_CONFIG.get("slave_id", 1)
                
                logger.debug("Lettura dati da Fase 1 (Stufa/Heater)...")
                heater_data = self.reader.read_all(phase=1, slave_id=slave_id)
                logger.debug(f"Risultato lettura heater: {heater_data is not None}")
                
                # Delay tra richieste a fasi diverse
                inter_request_delay = MODBUS_CONFIG.get("inter_request_delay", 0.2)
                if inter_request_delay > 0:
                    logger.debug(f"Attesa {inter_request_delay}s prima di leggere Fase 2...")
                    time.sleep(inter_request_delay)
                
                logger.debug("Lettura dati da Fase 2 (Ventilatore/Fan)...")
                fan_data = self.reader.read_all(phase=2, slave_id=slave_id)
                logger.debug(f"Risultato lettura fan: {fan_data is not None}")
                
                # Se entrambe le letture falliscono completamente, incrementa contatore errori
                # Ma considera anche letture parziali (es. potenza ok ma tensione no)
                if heater_data is None and fan_data is None:
                    consecutive_errors += 1
                    logger.warning(
                        f"Entrambe le letture fallite (heater e fan). "
                        f"Errori consecutivi: {consecutive_errors}/{max_consecutive_errors}"
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning(
                            f"{consecutive_errors} letture consecutive completamente fallite, "
                            "tentativo di riconnessione..."
                        )
                        try:
                            self.reader.disconnect()
                        except Exception as e:
                            logger.debug(f"Errore durante disconnessione: {e}")
                        if not self._reconnect():
                            logger.error("Riconnessione fallita dopo errori multipli")
                            time.sleep(self._sample_rate * 2)
                            continue
                        else:
                            consecutive_errors = 0
                else:
                    # Reset contatore errori se almeno una lettura riesce (anche parzialmente)
                    if consecutive_errors > 0:
                        logger.info(
                            f"Lettura riuscita dopo {consecutive_errors} errori. "
                            f"Heater: {heater_data is not None}, Fan: {fan_data is not None}"
                        )
                    consecutive_errors = 0
                
                # Salva misure su database
                if heater_data:
                    self._save_measurement(
                        self._current_session_id,
                        DeviceType.HEATER.value,
                        heater_data["power_w"],
                        voltage_v=heater_data.get("voltage_v"),
                        frequency_hz=heater_data.get("frequency_hz")
                    )
                
                if fan_data:
                    self._save_measurement(
                        self._current_session_id,
                        DeviceType.FAN.value,
                        fan_data["power_w"],
                        voltage_v=fan_data.get("voltage_v"),
                        frequency_hz=fan_data.get("frequency_hz")
                    )
                
                # Attendi prima della prossima lettura
                time.sleep(self._sample_rate)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Errore nel loop di acquisizione: {e}")
                
                # Se ci sono troppi errori consecutivi, tenta riconnessione
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(
                        f"{consecutive_errors} errori consecutivi, "
                        "tentativo di riconnessione..."
                    )
                    if self.reader:
                        try:
                            self.reader.disconnect()
                        except Exception:
                            pass
                    if not self._reconnect():
                        logger.error("Riconnessione fallita dopo errori multipli")
                        consecutive_errors = 0  # Reset per evitare loop infinito
                
                # Continua anche in caso di errore (non bloccare il loop)
                time.sleep(self._sample_rate)
        
        logger.info("Thread acquisizione terminato")
    
    def _reconnect(self) -> bool:
        """
        Tenta di riconnettere il dispositivo Modbus.
        
        Returns:
            True se riconnessione riuscita, False altrimenti
        """
        try:
            # Chiudi connessione esistente se presente
            if self.reader:
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
            
            # Crea nuovo reader e connetti
            self.reader = RSProReader(
                port=MODBUS_CONFIG["port"],
                baudrate=MODBUS_CONFIG["baudrate"],
                timeout=MODBUS_CONFIG["timeout"]
            )
            
            if self.reader.connect():
                logger.info("Riconnessione Modbus riuscita")
                return True
            else:
                logger.warning("Riconnessione Modbus fallita")
                return False
                
        except Exception as e:
            logger.error(f"Errore durante riconnessione: {e}")
            return False
    
    def _save_measurement(
        self,
        session_id: int,
        device_type: str,
        power_w: float,
        energy_kwh: Optional[float] = None,  # Non più letta, calcoliamo dalla potenza
        voltage_v: Optional[float] = None,
        frequency_hz: Optional[float] = None
    ):
        """
        Salva una misura su database.
        
        L'energia salvata è calcolata integrando la potenza nel tempo (energia della sessione),
        non l'energia totale accumulata del dispositivo.
        
        Args:
            session_id: ID sessione
            device_type: "heater" o "fan"
            power_w: Potenza in Watt
            energy_kwh: Energia letta dal dispositivo (non usata, calcoliamo dalla potenza)
            voltage_v: Tensione in Volt (opzionale)
            frequency_hz: Frequenza in Hz (opzionale)
        """
        try:
            # Calcola energia cumulata dalla potenza
            # Leggi l'ultima misurazione per questo device in questa sessione
            last_measurement = self.db.query(Measurement).filter(
                Measurement.session_id == session_id,
                Measurement.device_type == device_type
            ).order_by(Measurement.timestamp.desc()).first()
            
            current_timestamp = datetime.utcnow()
            
            if last_measurement:
                # Calcola incremento energia dall'ultima misurazione
                delta_time = (
                    current_timestamp - last_measurement.timestamp
                ).total_seconds() / 3600.0  # Converti in ore
                
                # Potenza media nell'intervallo (metodo del trapezio)
                avg_power = (last_measurement.power_w + power_w) / 2.0
                
                # Energia nell'intervallo = potenza media * tempo (in ore)
                # Risultato già in kWh (W * h / 1000 = kWh)
                energy_increment = (avg_power * delta_time) / 1000.0
                
                # Energia cumulata = energia precedente + incremento
                calculated_energy_kwh = last_measurement.energy_kwh + energy_increment
            else:
                # Prima misurazione della sessione: energia = 0
                calculated_energy_kwh = 0.0
            
            measurement = Measurement(
                session_id=session_id,
                device_type=device_type,
                power_w=power_w,
                energy_kwh=calculated_energy_kwh,  # Usa energia calcolata
                voltage_v=voltage_v,
                frequency_hz=frequency_hz,
                timestamp=current_timestamp
            )
            self.db.add(measurement)
            self.db.commit()
            
            logger.debug(
                f"Misura salvata: {device_type} - "
                f"Potenza: {power_w}W, "
                f"Energia calcolata: {calculated_energy_kwh:.4f}kWh"
            )
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

