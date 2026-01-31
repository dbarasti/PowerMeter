"""
Driver Modbus RTU per RS-PRO DIN Rail Multifunction Power Meter.
Gestisce comunicazione seriale, lettura registri e gestione errori.
Basato sulla documentazione RS-PRO Stock No: 236-9297.
Configurazione: Fase 1 = Stufa (Heater), Fase 2 = Ventilatore (Fan)

NOTA: Usa comunicazione seriale raw invece di pymodbus perché pymodbus
non funziona correttamente con questo dispositivo.
"""
import logging
import struct
import serial
import time
from typing import Optional, Dict

from app.config import MODBUS_CONFIG, ACQUISITION_CONFIG

logger = logging.getLogger(__name__)


class RSProError(Exception):
    """Eccezione personalizzata per errori RS-PRO."""
    pass


def calculate_crc(data):
    """Calcola CRC Modbus RTU."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def build_modbus_read_request(slave_id, function_code, start_address, num_registers):
    """Costruisce un frame Modbus RTU per Read Input Registers."""
    frame = bytearray([
        slave_id,
        function_code,
        (start_address >> 8) & 0xFF,  # Start address high
        start_address & 0xFF,         # Start address low
        (num_registers >> 8) & 0xFF,   # Number of registers high
        num_registers & 0xFF           # Number of registers low
    ])
    
    # Calcola CRC
    crc = calculate_crc(frame)
    frame.append(crc & 0xFF)      # CRC low
    frame.append((crc >> 8) & 0xFF)  # CRC high
    
    return bytes(frame)


def parse_modbus_response(data, slave_id, function_code):
    """Analizza la risposta Modbus e restituisce i registri."""
    if len(data) < 4:
        return None, "Risposta troppo corta"
    
    # Verifica slave ID
    if data[0] != slave_id:
        return None, f"Slave ID errato: atteso {slave_id}, ricevuto {data[0]}"
    
    # Verifica function code
    if data[1] != function_code:
        if data[1] == function_code | 0x80:  # Exception response
            exception_code = data[2]
            return None, f"Exception code: {exception_code}"
        return None, f"Function code errato: atteso {function_code}, ricevuto {data[1]}"
    
    # Verifica CRC
    received_crc = (data[-1] << 8) | data[-2]
    calculated_crc = calculate_crc(data[:-2])
    if received_crc != calculated_crc:
        return None, f"CRC errato: atteso {calculated_crc:04X}, ricevuto {received_crc:04X}"
    
    # Estrai dati
    byte_count = data[2]
    if len(data) < 3 + byte_count + 2:  # header + data + CRC
        return None, "Risposta incompleta"
    
    registers = []
    for i in range(0, byte_count, 2):
        if i + 1 < byte_count:
            high_byte = data[3 + i]
            low_byte = data[3 + i + 1]
            register = (high_byte << 8) | low_byte
            registers.append(register)
    
    return registers, None


class RSProReader:
    """
    Reader per RS-PRO DIN Rail Multifunction Power Meter via Modbus RTU.
    
    Modello: 236-9297
    Configurazione: Fase 1 = Stufa, Fase 2 = Ventilatore
    
    Registri RS-PRO (INPUT registers - 3X) - Documentazione 236-9297:
    
    Phase 1 (Stufa/Heater):
    - 0x0000 (0): Phase 1 line to neutral volts (V) - Modbus 30001-30002
    - 0x0006 (6): Phase 1 current (A) - Modbus 30007-30008
    - 0x0010 (16): Phase 1 active power (W) - Modbus 30017-30018 (CORRETTO - verificato)
    - 0x0012 (18): Phase 1 apparent power (VA) - Modbus 30019-30020
    - 0x016A (24): Phase 1 energy (kWh) - Modbus 30025-30026
    
    Phase 2 (Ventilatore/Fan):
    - 0x0002 (2): Phase 2 line to neutral volts (V) - Modbus 30003-30004
    - 0x0008 (8): Phase 2 current (A) - Modbus 30009-30010
    - 0x0012 (18): Phase 2 active power (W) - Modbus 30019-30020 (CORRETTO - +2 da Phase 1)
    - 0x0014 (20): Phase 2 apparent power (VA) - Modbus 30021-30022
    - 0x001A (26): Phase 2 energy (kWh) - Modbus 30027-30028
    
    Phase 3 (se presente):
    - 0x0004 (4): Phase 3 line to neutral volts (V) - Modbus 30005-30006
    - 0x000A (10): Phase 3 current (A) - Modbus 30011-30012
    - 0x0010 (16): Phase 3 active power (W) - Modbus 30017-30018
    - 0x0016 (22): Phase 3 apparent power (VA) - Modbus 30023-30024
    - 0x001C (28): Phase 3 energy (kWh) - Modbus 30029-30030
    
    Total System:
    - 0x0034 (52): Total system power (W) - Modbus 30053-30054
    - 0x0048 (72): Total Import kWh - Modbus 30073-30074
    - 0x004A (74): Total Export kWh - Modbus 30075-30076
    
    Nota: Ogni parametro occupa 2 registri consecutivi (float IEEE 754, 32-bit).
    IMPORTANTE: I registri sono in ordine Little-Endian (low register first, high register second).
    Questo è diverso dalla documentazione che dice "most significant register first" - 
    in pratica il dispositivo invia i registri invertiti rispetto alla documentazione.
    """
    
    # Indirizzi registri Modbus (offset 0-based)
    # Nota: gli indirizzi sono offset (0-based), non indirizzi Modbus (1-based)
    # Modbus address = offset + 30001
    
    # Phase 1 (Stufa/Heater) - Documentazione RS-PRO 236-9297
    REGISTER_PHASE1_VOLTAGE = 0x0000    # Modbus 30001-30002: Phase 1 line to neutral volts
    REGISTER_PHASE1_CURRENT = 0x0006    # Modbus 30007-30008: Phase 1 current
    REGISTER_PHASE1_POWER = 0x0010      # Modbus 30017-30018: Phase 1 active power (W) - CORRETTO
    REGISTER_PHASE1_ENERGY = 0x016A     # Modbus 30025-30026: Phase 1 energy (kWh)
    
    # Phase 2 (Ventilatore/Fan) - Documentazione RS-PRO 236-9297
    REGISTER_PHASE2_VOLTAGE = 0x0002    # Modbus 30003-30004: Phase 2 line to neutral volts
    REGISTER_PHASE2_CURRENT = 0x0008    # Modbus 30009-30010: Phase 2 current
    REGISTER_PHASE2_POWER = 0x0012      # Modbus 30019-30020: Phase 2 active power (W) - CORRETTO (+2 da Phase 1)
    REGISTER_PHASE2_ENERGY = 0x001A     # Modbus 30027-30028: Phase 2 energy (kWh)
    
    # Total System - Documentazione RS-PRO 236-9297
    REGISTER_TOTAL_POWER = 0x0034       # Modbus 30053-30054: Total system power (W)
    REGISTER_TOTAL_ENERGY_IMPORT = 0x0048  # Modbus 30073-30074: Total Import kWh
    REGISTER_TOTAL_ENERGY_EXPORT = 0x004A  # Modbus 30075-30076: Total Export kWh
    
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
        self.serial: Optional[serial.Serial] = None
        self._is_connected = False
    
    def connect(self) -> bool:
        """
        Apre la connessione seriale Modbus.
        
        Returns:
            True se connessione riuscita, False altrimenti
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=MODBUS_CONFIG["bytesize"],
                parity=MODBUS_CONFIG["parity"],
                stopbits=MODBUS_CONFIG["stopbits"],
                timeout=self.timeout,
            )
            
            # Pulisci buffer
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            time.sleep(0.5)  # Delay per stabilizzare
            
            self._is_connected = True
            logger.info(f"Modbus RTU connesso su {self.port} (RS-PRO)")
            
            # Delay dopo connessione per stabilizzare
            post_connect_delay = MODBUS_CONFIG.get("post_connect_delay", 0.5)
            if post_connect_delay > 0:
                time.sleep(post_connect_delay)
            
            return True
                
        except Exception as e:
            logger.warning(f"Errore connessione Modbus su {self.port}: {e}")
            self._is_connected = False
            return False
    
    def disconnect(self):
        """Chiude la connessione seriale."""
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
                self._is_connected = False
                logger.info("Connessione Modbus chiusa")
            except Exception as e:
                logger.error(f"Errore chiusura Modbus: {e}")
    
    def is_connected(self) -> bool:
        """Verifica se la connessione è attiva."""
        return self._is_connected and self.serial is not None and self.serial.is_open
    
    def _read_registers_raw(self, register: int, num_registers: int, slave_id: int) -> Optional[list]:
        """
        Legge registri Modbus usando comunicazione raw serial.
        
        Args:
            register: Offset registro (0-based)
            num_registers: Numero di registri da leggere
            slave_id: ID Modbus dello slave
            
        Returns:
            Lista di registri (16-bit words) o None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        try:
            # Pulisci buffer
            self.serial.reset_input_buffer()
            time.sleep(0.1)
            
            # Costruisci richiesta Modbus (Function 04 = Read Input Registers)
            request = build_modbus_read_request(slave_id, 0x04, register, num_registers)
            
            # Invia richiesta
            self.serial.write(request)
            self.serial.flush()
            
            # Attendi risposta
            start_time = time.time()
            response = b''
            
            while time.time() - start_time < self.timeout:
                if self.serial.in_waiting > 0:
                    chunk = self.serial.read(self.serial.in_waiting)
                    response += chunk
                    
                    # Verifica se è una risposta completa
                    if len(response) >= 4:
                        if response[1] == 0x04:  # Function code
                            byte_count = response[2]
                            expected_len = 3 + byte_count + 2  # header + data + CRC
                            if len(response) >= expected_len:
                                break
                        elif response[1] == 0x84:  # Exception
                            break
                
                time.sleep(0.01)
            
            if len(response) == 0:
                logger.warning(f"Nessuna risposta ricevuta per registro {register}")
                return None
            
            # Log risposta raw per debug
            logger.debug(
                f"Risposta raw (reg {register}): "
                f"{' '.join(f'{b:02X}' for b in response)} "
                f"({len(response)} bytes)"
            )
            
            # Analizza risposta
            registers, error = parse_modbus_response(response, slave_id, 0x04)
            
            if error:
                logger.warning(f"Errore parsing risposta per registro {register}: {error}")
                return None
            
            logger.debug(f"Registri estratti (reg {register}): {registers}")
            
            return registers
            
        except Exception as e:
            logger.error(f"Errore lettura registri {register}: {e}")
            return None
    
    def _read_float_register(self, register: int, phase: int, slave_id: int) -> Optional[float]:
        """
        Legge un registro float (2 registri consecutivi) e lo interpreta.
        
        Args:
            register: Offset registro (0-based)
            phase: Fase (1 o 2) - solo per logging
            slave_id: ID Modbus dello slave
            
        Returns:
            Valore float o None in caso di errore
        """
        registers = self._read_registers_raw(register, 2, slave_id)
        
        if registers is None or len(registers) != 2:
            return None
        
        # IMPORTANTE: RS-PRO invia registri in ordine Little-Endian
        # Il primo registro ricevuto è il HIGH word, il secondo è il LOW word
        # Quindi dobbiamo invertire l'ordine quando li interpretiamo come float
        high_word = registers[0]  # Primo registro = HIGH word
        low_word = registers[1]   # Secondo registro = LOW word
        
        # Log per debug
        logger.debug(
            f"Registri raw (reg {register}): "
            f"reg[0]={high_word} (0x{high_word:04X}), "
            f"reg[1]={low_word} (0x{low_word:04X})"
        )
        
        # Combina i registri in ordine corretto (low, high) e interpreta come float
        value_bytes = struct.pack('>HH', low_word, high_word)
        value = struct.unpack('>f', value_bytes)[0]
        
        logger.debug(f"Valore interpretato: {value}")
        
        return value
    
    def read_voltage(self, phase: int = 1, slave_id: int = 1) -> Optional[float]:
        """
        Legge la tensione (V) per una fase specifica.
        
        Args:
            phase: Fase da leggere (1 per stufa/heater, 2 per ventilatore/fan)
            slave_id: ID Modbus dello slave (default: 1)
            
        Returns:
            Tensione in Volt, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        # Seleziona il registro in base alla fase
        if phase == 1:
            register = self.REGISTER_PHASE1_VOLTAGE
            phase_name = "Fase 1 (Stufa)"
        elif phase == 2:
            register = self.REGISTER_PHASE2_VOLTAGE
            phase_name = "Fase 2 (Ventilatore)"
        else:
            logger.error(f"Fase non valida: {phase} (deve essere 1 o 2)")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                if attempt > 0:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"] * 1.5)
                
                voltage = self._read_float_register(register, phase, slave_id)
                
                if voltage is None:
                    logger.warning(f"Errore lettura tensione {phase_name} (tentativo {attempt + 1})")
                    continue
                
                # Verifica se il valore è plausibile (0-500V)
                if voltage < 0.0 or voltage > 500.0:
                    logger.warning(
                        f"Tensione anomala {phase_name}: {voltage}V da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura."
                    )
                    return None
                
                logger.debug(f"Tensione letta {phase_name}: {voltage}V da slave {slave_id}")
                return voltage
                
            except Exception as e:
                logger.warning(f"Eccezione lettura tensione {phase_name}: {e}")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
        
        return None
    
    def read_current(self, phase: int = 1, slave_id: int = 1) -> Optional[float]:
        """
        Legge la corrente (A) per una fase specifica.
        
        Args:
            phase: Fase da leggere (1 per stufa/heater, 2 per ventilatore/fan)
            slave_id: ID Modbus dello slave (default: 1)
            
        Returns:
            Corrente in Ampere, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        # Seleziona il registro in base alla fase
        if phase == 1:
            register = self.REGISTER_PHASE1_CURRENT
            phase_name = "Fase 1 (Stufa)"
        elif phase == 2:
            register = self.REGISTER_PHASE2_CURRENT
            phase_name = "Fase 2 (Ventilatore)"
        else:
            logger.error(f"Fase non valida: {phase} (deve essere 1 o 2)")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                if attempt > 0:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"] * 1.5)
                
                current = self._read_float_register(register, phase, slave_id)
                
                if current is None:
                    logger.warning(f"Errore lettura corrente {phase_name} (tentativo {attempt + 1})")
                    continue
                
                # Verifica se il valore è plausibile (0-1000A)
                if current < 0.0 or current > 1000.0:
                    logger.warning(
                        f"Corrente anomala {phase_name}: {current}A da slave {slave_id}."
                    )
                    return None
                
                logger.debug(f"Corrente letta {phase_name}: {current}A da slave {slave_id}")
                return current
                
            except Exception as e:
                logger.warning(f"Eccezione lettura corrente {phase_name}: {e}")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
        
        return None
    
    def read_power(self, phase: int = 1, slave_id: int = 1) -> Optional[float]:
        """
        Legge la potenza istantanea (W) per una fase specifica.
        
        Args:
            phase: Fase da leggere (1 per stufa/heater, 2 per ventilatore/fan)
            slave_id: ID Modbus dello slave (default: 1)
            
        Returns:
            Potenza in Watt, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        # Seleziona il registro in base alla fase
        if phase == 1:
            register = self.REGISTER_PHASE1_POWER
            phase_name = "Fase 1 (Stufa)"
        elif phase == 2:
            register = self.REGISTER_PHASE2_POWER
            phase_name = "Fase 2 (Ventilatore)"
        else:
            logger.error(f"Fase non valida: {phase} (deve essere 1 o 2)")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                if attempt > 0:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"] * 1.5)
                
                power_kw = self._read_float_register(register, phase, slave_id)
                
                if power_kw is None:
                    logger.warning(f"Errore lettura potenza {phase_name} (tentativo {attempt + 1})")
                    continue
                
                # IMPORTANTE: RS-PRO restituisce potenza in kW, convertiamo in W
                power = power_kw * 1000.0
                
                # Verifica se il valore è plausibile (0-100000W)
                if power < 0.0 or power > 100000.0:
                    logger.warning(
                        f"Potenza anomala {phase_name}: {power}W ({power_kw}kW) da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura."
                    )
                    return None
                
                logger.debug(
                    f"Potenza letta {phase_name}: {power}W ({power_kw}kW) da slave {slave_id}"
                )
                return power
                
            except Exception as e:
                logger.warning(f"Eccezione lettura potenza {phase_name}: {e}")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
        
        return None
    
    def read_energy(self, phase: int = 1, slave_id: int = 1) -> Optional[float]:
        """
        Legge l'energia cumulata (kWh) per una fase specifica.
        
        Args:
            phase: Fase da leggere (1 per stufa/heater, 2 per ventilatore/fan)
            slave_id: ID Modbus dello slave (default: 1)
            
        Returns:
            Energia in kWh, None in caso di errore
        """
        if not self.is_connected():
            logger.warning("Modbus non connesso")
            return None
        
        # Seleziona il registro in base alla fase
        if phase == 1:
            register = self.REGISTER_PHASE1_ENERGY
            phase_name = "Fase 1 (Stufa)"
        elif phase == 2:
            register = self.REGISTER_PHASE2_ENERGY
            phase_name = "Fase 2 (Ventilatore)"
        else:
            logger.error(f"Fase non valida: {phase} (deve essere 1 o 2)")
            return None
        
        for attempt in range(ACQUISITION_CONFIG["max_retries"]):
            try:
                if attempt > 0:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"] * 1.5)
                
                energy = self._read_float_register(register, phase, slave_id)
                
                if energy is None:
                    logger.warning(f"Errore lettura energia {phase_name} (tentativo {attempt + 1})")
                    continue
                
                # Verifica se il valore è plausibile (0-1000000kWh)
                if energy < 0.0 or energy > 1000000.0:
                    logger.warning(
                        f"Energia anomala {phase_name}: {energy}kWh da slave {slave_id}. "
                        f"Potrebbe essere un errore di lettura."
                    )
                    return None
                
                logger.debug(f"Energia letta {phase_name}: {energy}kWh da slave {slave_id}")
                return energy
                
            except Exception as e:
                logger.warning(f"Eccezione lettura energia {phase_name}: {e}")
                if attempt < ACQUISITION_CONFIG["max_retries"] - 1:
                    time.sleep(ACQUISITION_CONFIG["retry_delay"])
        
        return None
    
    def read_all(self, phase: int = 1, slave_id: int = 1) -> Optional[Dict[str, float]]:
        """
        Legge tensione e potenza per una fase specifica.
        
        Args:
            phase: Fase da leggere (1 per stufa/heater, 2 per ventilatore/fan)
            slave_id: ID Modbus dello slave (default: 1)
            
        Returns:
            Dizionario con i valori letti usando le chiavi attese dal codice di acquisizione:
            - "voltage_v": tensione in Volt
            - "power_w": potenza in Watt
            - "energy_kwh": None (non più letta dal dispositivo, calcolata dalla potenza)
            None in caso di errore
        """
        voltage = self.read_voltage(phase=phase, slave_id=slave_id)
        power = self.read_power(phase=phase, slave_id=slave_id)
        
        # Se almeno un valore è stato letto, restituisci il dizionario
        # Usa le chiavi attese dal codice di acquisizione
        if voltage is not None or power is not None:
            return {
                "voltage_v": voltage,
                "power_w": power,
                "energy_kwh": None,  # Non più letta, verrà calcolata dalla potenza
            }
        
        return None
