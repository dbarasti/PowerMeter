"""
Driver Modbus RTU per Eastron SDM120 power meter.
Gestisce comunicazione seriale, lettura registri e gestione errori.
"""
import logging
from typing import Optional, Dict
try:
    # pymodbus 3.x
    from pymodbus.client import ModbusSerialClient
    from pymodbus import Framer
    PYMODBUS_3X = True
except ImportError:
    # pymodbus 2.x fallback
    from pymodbus.client.sync import ModbusSerialClient
    PYMODBUS_3X = False
from pymodbus.exceptions import ModbusException
import time

from app.config import MODBUS_CONFIG, ACQUISITION_CONFIG

logger = logging.getLogger(__name__)


class SDM120Error(Exception):
    """Eccezione personalizzata per errori SDM120."""
    pass


class SDM120Reader:
    """
    Reader per Eastron SDM120 via Modbus RTU.
    
    Registri SDM120 (holding registers, 16-bit):
    - 0x0000: Voltage (V) - 1 decimal
    - 0x0006: Power (W) - 0 decimals
    - 0x0048: Total Active Energy (kWh) - 2 decimals
    
    Usiamo solo Power e Total Active Energy per questa applicazione.
    """
    
    # Indirizzi registri Modbus (decimali)
    REGISTER_VOLTAGE = 0x0000
    REGISTER_POWER = 0x0006
    REGISTER_ENERGY = 0x0048
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        """
        Inizializza il client Modbus RTU.
        
        Args:
            port: Porta seriale (es: "COM3" su Windows, "/dev/ttyUSB0" su Linux)
            baudrate: Velocità seriale
            timeout: Timeout lettura in secondi
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.client: Optional[ModbusSerialClient] = None
        self._is_connected = False
    
    def connect(self) -> bool:
        """
        Apre la connessione seriale Modbus.
        
        Returns:
            True se connessione riuscita, False altrimenti
        """
        try:
            if PYMODBUS_3X:
                # pymodbus 3.x API
                self.client = ModbusSerialClient(
                    port=self.port,
                    framer=Framer.RTU,
                    baudrate=self.baudrate,
                    bytesize=MODBUS_CONFIG["bytesize"],
                    parity=MODBUS_CONFIG["parity"],
                    stopbits=MODBUS_CONFIG["stopbits"],
                    timeout=self.timeout,
                )
                # In pymodbus 3.x, connect() restituisce None se OK
                result = self.client.connect()
                if result is not None and not result:
                    logger.warning(f"Impossibile connettersi a {self.port} (dispositivo non presente?)")
                    return False
            else:
                # pymodbus 2.x API
                self.client = ModbusSerialClient(
                    method="rtu",
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=MODBUS_CONFIG["bytesize"],
                    parity=MODBUS_CONFIG["parity"],
                    stopbits=MODBUS_CONFIG["stopbits"],
                    timeout=self.timeout,
                )
                if not self.client.connect():
                    logger.warning(f"Impossibile connettersi a {self.port} (dispositivo non presente?)")
                    return False
            
            self._is_connected = True
            logger.info(f"Modbus RTU connesso su {self.port}")
            return True
                
        except Exception as e:
            # Log come warning invece di error se è un problema di connessione normale
            logger.warning(f"Errore connessione Modbus su {self.port}: {e} (dispositivo non presente?)")
            self._is_connected = False
            return False
    
    def disconnect(self):
        """Chiude la connessione seriale."""
        if self.client:
            try:
                self.client.close()
                self._is_connected = False
                logger.info("Connessione Modbus chiusa")
            except Exception as e:
                logger.error(f"Errore chiusura Modbus: {e}")
    
    def is_connected(self) -> bool:
        """Verifica se la connessione è attiva."""
        return self._is_connected and self.client is not None
    
    def read_power(self, slave_id: int) -> Optional[float]:
        """
        Legge la potenza istantanea (W) da un SDM120.
        
        Args:
            slave_id: ID Modbus dello slave (1 o 2)
            
        Returns:
            Potenza in Watt, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                # Legge 1 holding register a partire da 0x0006
                result = self.client.read_holding_registers(
                    self.REGISTER_POWER,
                    1,
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura potenza (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce valore come intero (W)
                power = float(result.registers[0])
                return power
                
            except ModbusException as e:
                logger.warning(f"ModbusException lettura potenza: {e} (tentativo {attempt + 1})")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
            except Exception as e:
                logger.error(f"Errore imprevisto lettura potenza: {e}")
                return None
        
        return None
    
    def read_energy(self, slave_id: int) -> Optional[float]:
        """
        Legge l'energia accumulata (kWh) da un SDM120.
        
        Args:
            slave_id: ID Modbus dello slave (1 o 2)
            
        Returns:
            Energia in kWh, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                # Legge 2 holding registers a partire da 0x0048 (32-bit value)
                result = self.client.read_holding_registers(
                    self.REGISTER_ENERGY,
                    2,
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura energia (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce energia come 32-bit (2 registri)
                # High word, Low word
                high_word = result.registers[0]
                low_word = result.registers[1]
                # Combina i due registri (high << 16 | low)
                energy_raw = (high_word << 16) | low_word
                # Converti in kWh (valore è in Wh * 100, quindi dividi per 100000)
                energy = energy_raw / 100000.0
                return energy
                
            except ModbusException as e:
                logger.warning(f"ModbusException lettura energia: {e} (tentativo {attempt + 1})")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
            except Exception as e:
                logger.error(f"Errore imprevisto lettura energia: {e}")
                return None
        
        return None
    
    def read_all(self, slave_id: int) -> Optional[Dict[str, float]]:
        """
        Legge potenza ed energia in una singola chiamata.
        
        Args:
            slave_id: ID Modbus dello slave
            
        Returns:
            Dict con 'power_w' e 'energy_kwh', None in caso di errore
        """
        power = self.read_power(slave_id)
        energy = self.read_energy(slave_id)
        
        if power is None or energy is None:
            return None
        
        return {
            "power_w": power,
            "energy_kwh": energy,
        }

