"""
Driver Modbus RTU per Eastron SDM120 power meter.
Gestisce comunicazione seriale, lettura registri e gestione errori.
"""
import logging
import struct
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
    
    Registri SDM120 (INPUT registers):
    - 0x0000: Voltage (V) - IEEE 754 float 32-bit (2 registri) - Modbus 30001
    - 0x000C: Active Power (W) - IEEE 754 float 32-bit (2 registri) - Modbus 30013
    - 0x0046: Frequency (Hz) - IEEE 754 float 32-bit (2 registri) - Modbus 30071
    - 0x0048: Total Active Energy (kWh) - IEEE 754 float 32-bit (2 registri) - Modbus 30073
    """
    
    # Indirizzi registri Modbus (decimali)
    # Nota: gli indirizzi sono offset (0-based), non indirizzi Modbus (1-based)
    REGISTER_VOLTAGE = 0x0000  # Modbus address 30001
    REGISTER_POWER = 0x000C    # Modbus address 30013 (Active Power in W)
    REGISTER_FREQUENCY = 0x0046  # Modbus address 30071
    REGISTER_ENERGY = 0x0048    # Modbus address 30073
    
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
        """
        Verifica se la connessione è attiva.
        Controlla anche che il client seriale sia effettivamente connesso.
        """
        if not self._is_connected or self.client is None:
            return False
        
        # Verifica che il client sia effettivamente connesso
        # (pymodbus può avere il flag ma la connessione seriale può essere caduta)
        try:
            # Prova a verificare lo stato della connessione
            # In pymodbus 3.x, is_socket_open() verifica lo stato
            if hasattr(self.client, 'is_socket_open'):
                return self.client.is_socket_open()
            # Fallback: se non disponibile, usa il flag interno
            return self._is_connected
        except Exception:
            # Se c'è un errore nel controllo, considera disconnesso
            self._is_connected = False
            return False
    
    def read_power(self, slave_id: int) -> Optional[float]:
        """
        Legge la potenza istantanea (W) da un SDM120.
        Nota: SDM120 usa INPUT REGISTERS e valori in formato IEEE 754 float (32-bit).
        
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
                # SDM120 usa INPUT REGISTERS per i valori di misura
                # Register 0x000C (30013): Active Power (W) - formato IEEE 754 float (32-bit = 2 registri)
                result = self.client.read_input_registers(
                    self.REGISTER_POWER,
                    2,  # Legge 2 registri per float 32-bit
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura potenza (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce valori in formato IEEE 754 float (32-bit)
                high_word = result.registers[0]
                low_word = result.registers[1]
                
                # Log per debug
                logger.debug(
                    f"Potenza raw da slave {slave_id}: "
                    f"high={high_word} (0x{high_word:04X}), "
                    f"low={low_word} (0x{low_word:04X})"
                )
                
                # Prova prima Big-Endian (standard SDM120)
                power_bytes = struct.pack('>HH', high_word, low_word)
                power = struct.unpack('>f', power_bytes)[0]
                
                # Se il valore sembra anomalo (troppo piccolo o negativo), prova Little-Endian
                if power < 0 or (power > 0 and power < 0.1):
                    logger.debug(f"Tentativo Little-Endian per potenza (valore BE: {power}W)")
                    power_bytes_le = struct.pack('<HH', high_word, low_word)
                    power_le = struct.unpack('<f', power_bytes_le)[0]
                    if power_le > 0 and power_le < 100000:  # Valore plausibile
                        logger.info(f"Usando Little-Endian per potenza: {power_le}W (BE era {power}W)")
                        power = power_le
                
                logger.debug(f"Potenza letta: {power}W da slave {slave_id}")
                
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
        Nota: SDM120 usa INPUT REGISTERS e valori in formato IEEE 754 float (32-bit).
        
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
                # SDM120 usa INPUT REGISTERS per i valori di misura
                # Register 0x0048: Total Active Energy (kWh) - formato IEEE 754 float (32-bit = 2 registri)
                result = self.client.read_input_registers(
                    self.REGISTER_ENERGY,
                    2,  # Legge 2 registri per float 32-bit
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura energia (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce valori in formato IEEE 754 float (32-bit)
                high_word = result.registers[0]
                low_word = result.registers[1]
                # Combina i due registri in un float (Big-Endian)
                energy_bytes = struct.pack('>HH', high_word, low_word)
                energy = struct.unpack('>f', energy_bytes)[0]
                
                return energy
                
            except ModbusException as e:
                logger.warning(f"ModbusException lettura energia: {e} (tentativo {attempt + 1})")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
            except Exception as e:
                logger.error(f"Errore imprevisto lettura energia: {e}")
                return None
        
        return None
    
    def read_voltage(self, slave_id: int) -> Optional[float]:
        """
        Legge la tensione (V) da un SDM120.
        Nota: SDM120 usa INPUT REGISTERS e valori in formato IEEE 754 float (32-bit).
        
        Args:
            slave_id: ID Modbus dello slave (1 o 2)
            
        Returns:
            Tensione in Volt, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                # SDM120 usa INPUT REGISTERS per i valori di misura
                # Register 0x0000: Voltage (V) - formato IEEE 754 float (32-bit = 2 registri)
                result = self.client.read_input_registers(
                    self.REGISTER_VOLTAGE,
                    2,  # Legge 2 registri per float 32-bit
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura tensione (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce valori in formato IEEE 754 float (32-bit)
                # I registri sono in ordine Big-Endian: [High word, Low word]
                high_word = result.registers[0]
                low_word = result.registers[1]
                # Combina i due registri in un float (Big-Endian)
                # struct.pack crea bytes, struct.unpack interpreta come float
                voltage_bytes = struct.pack('>HH', high_word, low_word)  # > = big-endian, HH = 2 unsigned short
                voltage = struct.unpack('>f', voltage_bytes)[0]  # f = float
                
                # Verifica se il valore è plausibile (0-500V)
                if voltage < 0.0 or voltage > 500.0:
                    logger.warning(
                        f"Tensione anomala: {voltage}V da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura o dispositivo non collegato."
                    )
                    return None
                
                # Log per debug
                logger.debug(f"Tensione letta: {voltage}V da slave {slave_id}")
                
                return voltage
                
            except ModbusException as e:
                logger.warning(f"ModbusException lettura tensione: {e} (tentativo {attempt + 1})")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
            except Exception as e:
                logger.error(f"Errore imprevisto lettura tensione: {e}")
                return None
        
        return None
    
    def read_frequency(self, slave_id: int) -> Optional[float]:
        """
        Legge la frequenza (Hz) da un SDM120.
        Nota: SDM120 usa INPUT REGISTERS e valori in formato IEEE 754 float (32-bit).
        
        Args:
            slave_id: ID Modbus dello slave (1 o 2)
            
        Returns:
            Frequenza in Hz, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                # SDM120 usa INPUT REGISTERS per i valori di misura
                # Register 0x000C: Frequency (Hz) - formato IEEE 754 float (32-bit = 2 registri)
                result = self.client.read_input_registers(
                    self.REGISTER_FREQUENCY,
                    2,  # Legge 2 registri per float 32-bit
                    unit=slave_id
                )
                
                if result.isError():
                    logger.warning(f"Errore lettura frequenza (tentativo {attempt + 1})")
                    if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                        time.sleep(ACQUISITION_CONFIG["retry_delay"])
                    continue
                
                # SDM120 restituisce valori in formato IEEE 754 float (32-bit)
                high_word = result.registers[0]
                low_word = result.registers[1]
                
                # Log per debug
                logger.debug(
                    f"Frequenza raw da slave {slave_id}: "
                    f"high={high_word} (0x{high_word:04X}), "
                    f"low={low_word} (0x{low_word:04X})"
                )
                
                # Combina i due registri in un float (Big-Endian)
                frequency_bytes = struct.pack('>HH', high_word, low_word)
                frequency = struct.unpack('>f', frequency_bytes)[0]
                
                # Log sempre per diagnosticare
                logger.info(
                    f"Frequenza letta: {frequency}Hz (raw: {high_word}, {low_word}) "
                    f"da slave {slave_id}"
                )
                
                # Verifica se il valore è plausibile (45-55Hz)
                # Se è 0.0, potrebbe essere un errore di lettura o registro sbagliato
                if frequency == 0.0:
                    logger.warning(
                        f"Frequenza letta come 0.0Hz da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura o registro errato."
                    )
                    # Non restituiamo None per 0, ma loggiamo il warning
                    # Potrebbe essere che il dispositivo non misuri la frequenza
                
                if frequency < 0.0 or (frequency > 55.0 and frequency != 0.0):
                    logger.warning(
                        f"Frequenza anomala: {frequency}Hz da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura."
                    )
                    return None
                
                return frequency
                
            except ModbusException as e:
                logger.warning(f"ModbusException lettura frequenza: {e} (tentativo {attempt + 1})")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
            except Exception as e:
                logger.error(f"Errore imprevisto lettura frequenza: {e}")
                return None
        
        return None
    
    def read_all(self, slave_id: int) -> Optional[Dict[str, float]]:
        """
        Legge tutti i parametri (tensione, frequenza, potenza, energia) in una singola chiamata.
        
        Args:
            slave_id: ID Modbus dello slave
            
        Returns:
            Dict con 'voltage_v', 'frequency_hz', 'power_w' e 'energy_kwh', None in caso di errore
        """
        voltage = self.read_voltage(slave_id)
        frequency = self.read_frequency(slave_id)
        power = self.read_power(slave_id)
        energy = self.read_energy(slave_id)
        
        # Considera la lettura valida se almeno potenza ed energia sono disponibili
        if power is None or energy is None:
            logger.debug(f"Lettura fallita per slave {slave_id}: power={power}, energy={energy}")
            return None
        
        # Verifica che i valori siano plausibili
        # Se tensione è > 500V, è chiaramente un errore
        if voltage is not None and voltage > 500.0:
            logger.warning(
                f"Tensione anomala {voltage}V da slave {slave_id}. "
                f"Impostando a None."
            )
            voltage = None
        
        # Se frequenza è fuori range 45-55Hz, potrebbe essere un errore
        if frequency is not None and (frequency < 45.0 or frequency > 55.0):
            logger.warning(
                f"Frequenza anomala {frequency}Hz da slave {slave_id}. "
                f"Impostando a None."
            )
            frequency = None
        
        return {
            "voltage_v": voltage,
            "frequency_hz": frequency,
            "power_w": power,
            "energy_kwh": energy,
        }

