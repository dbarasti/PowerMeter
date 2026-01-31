#!/usr/bin/env python3
"""
Script di diagnostica dettagliata per problemi di comunicazione Modbus RS-PRO.
Verifica trasmissione, ricezione, slave ID, cablaggio, etc.
"""
import sys
import time
import struct
import logging
from pathlib import Path

# Aggiungi il path dell'app al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from app.config import MODBUS_CONFIG

# Configura logging molto dettagliato
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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


def test_basic_communication(client, slave_id: int, timeout: float = 5.0):
    """
    Test base di comunicazione con un singolo registro.
    
    Returns:
        Tuple (success, response, error_message)
    """
    print(f"\n{'='*80}")
    print(f"TEST COMUNICAZIONE BASE - Slave ID {slave_id}")
    print(f"{'='*80}")
    
    try:
        print(f"Invio richiesta: read_input_registers(0x0000, 2, unit={slave_id})")
        print(f"Timeout: {timeout}s")
        
        start_time = time.time()
        result = client.read_input_registers(0x0000, 2, unit=slave_id)
        elapsed = time.time() - start_time
        
        print(f"Tempo trascorso: {elapsed:.3f}s")
        
        if result.isError():
            error_msg = str(result)
            if hasattr(result, 'message'):
                error_msg = result.message
            print(f"❌ ERRORE nella risposta: {error_msg}")
            return False, None, error_msg
        else:
            print(f"✅ RISPOSTA RICEVUTA!")
            print(f"   Registri: {result.registers}")
            print(f"   Numero registri: {len(result.registers)}")
            
            if len(result.registers) == 2:
                # IMPORTANTE: RS-PRO invia registri in ordine Little-Endian
                # Primo registro = LOW word, Secondo registro = HIGH word
                low_word = result.registers[0]
                high_word = result.registers[1]
                print(f"   Registro 0 (LOW): {low_word} (0x{low_word:04X})")
                print(f"   Registro 1 (HIGH): {high_word} (0x{high_word:04X})")
                
                # Interpreta in Little-Endian (low, high)
                try:
                    value_bytes = struct.pack('>HH', low_word, high_word)
                    value = struct.unpack('>f', value_bytes)[0]
                    print(f"   Valore: {value:.4f}")
                except Exception as e:
                    print(f"   Errore interpretazione float: {e}")
            
            return True, result, None
            
    except ModbusException as e:
        print(f"❌ ModbusException: {type(e).__name__}: {e}")
        return False, None, str(e)
    except Exception as e:
        print(f"❌ Eccezione generica: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, None, str(e)


def test_multiple_slave_ids(client, timeout: float = 5.0):
    """
    Testa diversi slave ID per trovare quello corretto.
    """
    print(f"\n{'='*80}")
    print("TEST MULTIPLI SLAVE ID")
    print(f"{'='*80}")
    print("Verificando quale slave ID risponde...")
    print()
    
    # Testa slave ID comuni
    slave_ids_to_test = [1, 2, 3, 9, 10, 247]
    
    responding_slaves = []
    
    for slave_id in slave_ids_to_test:
        print(f"  → Test slave ID {slave_id}...", end=" ", flush=True)
        
        try:
            result = client.read_input_registers(0x0000, 2, unit=slave_id)
            
            if result.isError():
                error_msg = str(result)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    print("⏱️  TIMEOUT (nessuna risposta)")
                else:
                    print(f"❌ ERRORE: {error_msg[:50]}")
            else:
                print(f"✅ RISPOSTA!")
                print(f"      Registri: {result.registers}")
                responding_slaves.append((slave_id, result))
        except ModbusException as e:
            print(f"❌ ModbusException: {type(e).__name__}")
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}")
        
        time.sleep(0.3)  # Delay tra test
    
    print()
    if responding_slaves:
        print(f"✅ Trovati {len(responding_slaves)} slave ID che rispondono:")
        for slave_id, result in responding_slaves:
            print(f"   Slave ID {slave_id}: {result.registers}")
    else:
        print("❌ Nessuno slave ID ha risposto")
        print("   Possibili cause:")
        print("   - Slave ID errato")
        print("   - Cablaggio RS485 errato (A/B invertiti?)")
        print("   - Dispositivo non alimentato")
        print("   - Configurazione Modbus errata (baudrate, parity, etc.)")
    
    return responding_slaves


def test_different_registers(client, slave_id: int, timeout: float = 5.0):
    """
    Testa diversi registri per vedere se qualcuno risponde.
    """
    print(f"\n{'='*80}")
    print(f"TEST REGISTRI DIVERSI - Slave ID {slave_id}")
    print(f"{'='*80}")
    
    registers_to_test = [
        (0x0000, "Phase 1 Voltage"),
        (0x0002, "Phase 2 Voltage"),
        (0x0006, "Phase 1 Current"),
        (0x000C, "Phase 1 Power"),
        (0x0034, "Total Power"),
        (0x0048, "Total Energy Import"),
    ]
    
    successful_reads = []
    
    for reg, description in registers_to_test:
        modbus_addr = 30001 + reg
        print(f"  → Test registro {reg:04X} (Modbus {modbus_addr:05d}): {description}...", end=" ", flush=True)
        
        try:
            result = client.read_input_registers(reg, 2, unit=slave_id)
            
            if result.isError():
                error_msg = str(result)
                if "timeout" in error_msg.lower():
                    print("⏱️  TIMEOUT")
                else:
                    print(f"❌ ERRORE: {error_msg[:40]}")
            else:
                print(f"✅ OK - Registri: {result.registers}")
                successful_reads.append((reg, description, result))
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}")
        
        time.sleep(0.2)
    
    print()
    if successful_reads:
        print(f"✅ {len(successful_reads)} registri hanno risposto correttamente")
    else:
        print("❌ Nessun registro ha risposto")
    
    return successful_reads


def test_timeout_settings(client, slave_id: int):
    """
    Testa con timeout diversi per vedere se il problema è il timeout.
    """
    print(f"\n{'='*80}")
    print("TEST TIMEOUT DIVERSI")
    print(f"{'='*80}")
    
    timeouts = [1.0, 2.0, 3.0, 5.0, 10.0]
    
    for timeout in timeouts:
        print(f"\nTest con timeout {timeout}s...", end=" ", flush=True)
        try:
            # Modifica timeout temporaneamente
            if hasattr(client, 'socket') and client.socket:
                client.socket.timeout = timeout
            elif hasattr(client, 'serial') and client.serial:
                client.serial.timeout = timeout
            
            result = client.read_input_registers(0x0000, 2, unit=slave_id)
            
            if result.isError():
                error_msg = str(result)
                if "timeout" in error_msg.lower():
                    print("⏱️  TIMEOUT")
                else:
                    print(f"❌ ERRORE: {error_msg[:40]}")
            else:
                print(f"✅ SUCCESSO! Registri: {result.registers}")
                return timeout
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}")
    
    return None


def test_serial_settings():
    """
    Testa diverse configurazioni seriali.
    """
    print(f"\n{'='*80}")
    print("TEST CONFIGURAZIONI SERIALI")
    print(f"{'='*80}")
    
    # Configurazioni da testare
    configs = [
        {"parity": "N", "stopbits": 1, "bytesize": 8},
        {"parity": "E", "stopbits": 1, "bytesize": 8},
        {"parity": "O", "stopbits": 1, "bytesize": 8},
        {"parity": "N", "stopbits": 2, "bytesize": 8},
    ]
    
    for config in configs:
        print(f"\nTest configurazione: {config}")
        try:
            if PYMODBUS_3X:
                client = ModbusSerialClient(
                    port=MODBUS_CONFIG["port"],
                    framer=Framer.RTU,
                    baudrate=MODBUS_CONFIG["baudrate"],
                    bytesize=config["bytesize"],
                    parity=config["parity"],
                    stopbits=config["stopbits"],
                    timeout=5.0,
                )
                result = client.connect()
                if result is not None and not result:
                    print("  ❌ Connessione fallita")
                    continue
            else:
                client = ModbusSerialClient(
                    method="rtu",
                    port=MODBUS_CONFIG["port"],
                    baudrate=MODBUS_CONFIG["baudrate"],
                    bytesize=config["bytesize"],
                    parity=config["parity"],
                    stopbits=config["stopbits"],
                    timeout=5.0,
                )
                if not client.connect():
                    print("  ❌ Connessione fallita")
                    continue
            
            time.sleep(0.5)
            
            # Prova a leggere
            result = client.read_input_registers(0x0000, 2, unit=1)
            if result.isError():
                print(f"  ❌ Errore: {result}")
            else:
                print(f"  ✅ SUCCESSO! Registri: {result.registers}")
                client.close()
                return config
            
            client.close()
        except Exception as e:
            print(f"  ❌ Eccezione: {e}")
    
    return None


def main():
    """Funzione principale di diagnostica."""
    print("=" * 80)
    print("DIAGNOSTICA RS-PRO MODBUS - Problemi di Comunicazione")
    print("=" * 80)
    print(f"Porta: {MODBUS_CONFIG['port']}")
    print(f"Baudrate: {MODBUS_CONFIG['baudrate']}")
    print(f"Bytesize: {MODBUS_CONFIG['bytesize']}")
    print(f"Parity: {MODBUS_CONFIG['parity']}")
    print(f"Stopbits: {MODBUS_CONFIG['stopbits']}")
    print(f"Timeout: {MODBUS_CONFIG['timeout']}s")
    slave_id = MODBUS_CONFIG.get("slave_id", 1)
    print(f"Slave ID configurato: {slave_id}")
    print("=" * 80)
    print()
    
    # Crea client Modbus
    print("Creazione client Modbus...")
    try:
        if PYMODBUS_3X:
            client = ModbusSerialClient(
                port=MODBUS_CONFIG["port"],
                framer=Framer.RTU,
                baudrate=MODBUS_CONFIG["baudrate"],
                bytesize=MODBUS_CONFIG["bytesize"],
                parity=MODBUS_CONFIG["parity"],
                stopbits=MODBUS_CONFIG["stopbits"],
                timeout=MODBUS_CONFIG["timeout"],
            )
            result = client.connect()
            if result is not None and not result:
                print("❌ ERRORE: Impossibile connettersi alla porta seriale")
                return False
        else:
            client = ModbusSerialClient(
                method="rtu",
                port=MODBUS_CONFIG["port"],
                baudrate=MODBUS_CONFIG["baudrate"],
                bytesize=MODBUS_CONFIG["bytesize"],
                parity=MODBUS_CONFIG["parity"],
                stopbits=MODBUS_CONFIG["stopbits"],
                timeout=MODBUS_CONFIG["timeout"],
            )
            if not client.connect():
                print("❌ ERRORE: Impossibile connettersi alla porta seriale")
                return False
        
        print("✅ Connessione seriale stabilita")
        print()
        
        # Delay dopo connessione
        time.sleep(1.0)
        
        # Test 1: Comunicazione base con slave ID configurato
        success, response, error = test_basic_communication(client, slave_id, timeout=5.0)
        
        if not success:
            print("\n⚠️  La comunicazione base è fallita. Eseguendo test diagnostici...")
            
            # Test 2: Prova diversi slave ID
            responding_slaves = test_multiple_slave_ids(client, timeout=5.0)
            
            if responding_slaves:
                # Se troviamo un slave ID che risponde, usalo per i test successivi
                found_slave_id, _ = responding_slaves[0]
                print(f"\n✅ Usando slave ID {found_slave_id} per i test successivi")
                slave_id = found_slave_id
            else:
                # Test 3: Prova diverse configurazioni seriali
                print("\n⚠️  Nessuno slave ID risponde. Test configurazioni seriali...")
                working_config = test_serial_settings()
                
                if working_config:
                    print(f"\n✅ Configurazione funzionante trovata: {working_config}")
                else:
                    print("\n❌ Nessuna configurazione seriale funziona")
                    print("\n💡 SUGGERIMENTI:")
                    print("   1. Verifica il cablaggio RS485:")
                    print("      - A+ deve essere collegato ad A+")
                    print("      - B- deve essere collegato a B-")
                    print("      - Prova a invertire A e B se non funziona")
                    print("   2. Verifica lo slave ID sul display del RS-PRO")
                    print("   3. Verifica che il dispositivo sia alimentato")
                    print("   4. Verifica baudrate, parity, stopbits nella configurazione RS-PRO")
                    print("   5. Controlla se ci sono terminazioni RS485 (120 ohm)")
                    client.close()
                    return False
        
        # Test 4: Test timeout diversi
        if not success:
            print("\n⚠️  Test timeout diversi...")
            working_timeout = test_timeout_settings(client, slave_id)
            if working_timeout:
                print(f"\n✅ Timeout funzionante trovato: {working_timeout}s")
        
        # Test 5: Test diversi registri
        if success or (responding_slaves and len(responding_slaves) > 0):
            test_different_registers(client, slave_id, timeout=5.0)
        
        # Chiudi connessione
        client.close()
        print("\n✅ Diagnostica completata")
        
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        return False
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
