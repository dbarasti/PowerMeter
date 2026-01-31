#!/usr/bin/env python3
"""
Script di test per verificare i registri Modbus del RS-PRO.
Legge da vari registri per identificare quelli corretti per potenza, energia, tensione, etc.
"""
import sys
import time
import struct
import logging
from pathlib import Path

# Aggiungi il path dell'app al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from app.config import MODBUS_CONFIG
from app.modbus.rspro import RSProReader

# Configura logging dettagliato
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def read_register_as_float(reader, register: int, slave_id: int = 1, description: str = ""):
    """
    Legge un registro come float IEEE 754 e restituisce il valore.
    
    Args:
        reader: RSProReader instance
        register: Offset registro (0-based)
        slave_id: ID Modbus slave
        description: Descrizione del registro
        
    Returns:
        Tuple (success, value, raw_registers)
    """
    try:
        result = reader.client.read_input_registers(register, 2, unit=slave_id)
        
        if result.isError():
            return False, None, None
        
        # IMPORTANTE: RS-PRO invia registri in ordine Little-Endian
        # Primo registro = LOW word, Secondo registro = HIGH word
        low_word = result.registers[0]
        high_word = result.registers[1]
        
        # Interpreta in Little-Endian (low, high)
        value_bytes = struct.pack('>HH', low_word, high_word)
        value = struct.unpack('>f', value_bytes)[0]
        
        return True, value, (low_word, high_word)
        
    except Exception as e:
        return False, None, str(e)


def test_register_range(reader, start_reg: int, end_reg: int, slave_id: int = 1, step: int = 2):
    """
    Testa un range di registri e mostra quelli con valori plausibili.
    
    Args:
        reader: RSProReader instance
        start_reg: Registro iniziale (offset 0-based)
        end_reg: Registro finale (offset 0-based)
        slave_id: ID Modbus slave
        step: Step tra registri (2 per float, 1 per vedere tutti)
    """
    print(f"\n{'='*80}")
    print(f"Test registri da {start_reg} (30001) a {end_reg} (30001+{end_reg})")
    print(f"{'='*80}\n")
    
    found_values = []
    
    for reg in range(start_reg, end_reg + 1, step):
        modbus_addr = 30001 + reg
        success, value, raw = read_register_as_float(reader, reg, slave_id)
        
        if success and value is not None:
            # Filtra valori plausibili
            abs_value = abs(value)
            is_plausible = False
            value_type = "?"
            
            # Potenza: 0-100000W
            if 0 <= abs_value <= 100000:
                is_plausible = True
                value_type = "Potenza (W)"
            # Tensione: 0-500V
            elif 0 <= abs_value <= 500:
                is_plausible = True
                value_type = "Tensione (V)"
            # Corrente: 0-1000A
            elif 0 <= abs_value <= 1000:
                is_plausible = True
                value_type = "Corrente (A)"
            # Energia: 0-1000000kWh
            elif 0 <= abs_value <= 1000000:
                is_plausible = True
                value_type = "Energia (kWh)"
            # Frequenza: 45-55Hz
            elif 45 <= abs_value <= 55:
                is_plausible = True
                value_type = "Frequenza (Hz)"
            
            if is_plausible:
                found_values.append((reg, modbus_addr, value, value_type, raw))
                print(f"✅ Registro {reg:04X} (Modbus {modbus_addr:05d}): "
                      f"{value:12.4f} {value_type:20s} "
                      f"[Raw: {raw[0]:04X} {raw[1]:04X}]")
        
        time.sleep(0.05)  # Piccolo delay tra letture
    
    return found_values


def test_specific_registers(reader, slave_id: int = 1):
    """
    Testa registri specifici comuni per power meter trifase.
    """
    print(f"\n{'='*80}")
    print("Test registri specifici comuni per power meter trifase")
    print(f"{'='*80}\n")
    
    # Registri comuni da testare
    test_registers = [
        # Phase 1
        (0x0000, "Phase 1 Voltage"),
        (0x0006, "Phase 1 Current"),
        (0x000C, "Phase 1 Active Power"),
        (0x0012, "Phase 1 Apparent Power"),
        (0x0018, "Phase 1 Energy"),
        
        # Phase 2
        (0x0002, "Phase 2 Voltage"),
        (0x0008, "Phase 2 Current"),
        (0x000E, "Phase 2 Active Power"),
        (0x0014, "Phase 2 Apparent Power"),
        (0x001A, "Phase 2 Energy"),
        
        # Phase 3
        (0x0004, "Phase 3 Voltage"),
        (0x000A, "Phase 3 Current"),
        (0x0010, "Phase 3 Active Power"),
        (0x0016, "Phase 3 Apparent Power"),
        (0x001C, "Phase 3 Energy"),
        
        # Total System
        (0x0034, "Total System Power"),
        (0x0048, "Total Import Energy"),
        (0x004A, "Total Export Energy"),
        
        # Altri registri comuni
        (0x0046, "Frequency"),
        (0x004C, "Total Energy"),
    ]
    
    results = []
    
    for reg, description in test_registers:
        modbus_addr = 30001 + reg
        success, value, raw = read_register_as_float(reader, reg, slave_id, description)
        
        if success and value is not None:
            status = "✅" if abs(value) < 1000000 else "⚠️"
            print(f"{status} {reg:04X} (Modbus {modbus_addr:05d}): {description:30s} = "
                  f"{value:12.4f} [Raw: {raw[0]:04X} {raw[1]:04X}]")
            results.append((reg, modbus_addr, description, value, raw))
        else:
            print(f"❌ {reg:04X} (Modbus {modbus_addr:05d}): {description:30s} = ERRORE")
        
        time.sleep(0.1)  # Delay tra letture
    
    return results


def test_slave_ids(reader):
    """
    Testa diversi slave ID per trovare quello corretto.
    
    Returns:
        Lista di tuple (slave_id, result) per slave ID che rispondono
    """
    print(f"\n{'='*80}")
    print("TEST SLAVE ID - Verifica quale dispositivo risponde")
    print(f"{'='*80}\n")
    print("Verificando quale slave ID risponde...")
    print()
    
    # Testa slave ID comuni (puoi espandere questo range)
    slave_ids_to_test = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 247]
    
    responding_slaves = []
    
    for slave_id in slave_ids_to_test:
        print(f"  → Test slave ID {slave_id:3d}...", end=" ", flush=True)
        
        try:
            result = reader.client.read_input_registers(0x0000, 2, unit=slave_id)
            
            if result.isError():
                error_msg = str(result)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    print("⏱️  TIMEOUT")
                else:
                    print(f"❌ ERRORE")
            else:
                print(f"✅ RISPOSTA!")
                print(f"      Registri: {result.registers}")
                responding_slaves.append((slave_id, result))
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}")
        
        time.sleep(0.2)  # Delay tra test
    
    print()
    if responding_slaves:
        print(f"✅ Trovati {len(responding_slaves)} slave ID che rispondono:")
        for slave_id, result in responding_slaves:
            print(f"   Slave ID {slave_id}: Registri {result.registers}")
        print()
        print("💡 Userò il primo slave ID trovato per i test successivi")
    else:
        print("❌ Nessuno slave ID ha risposto")
        print("   Possibili cause:")
        print("   - Slave ID errato")
        print("   - Cablaggio RS485 errato (A/B invertiti?)")
        print("   - Dispositivo non alimentato")
        print("   - Configurazione Modbus errata (baudrate, parity, etc.)")
        print()
    
    return responding_slaves


def main():
    """Funzione principale di test."""
    print("=" * 80)
    print("Test Registri RS-PRO Modbus")
    print("=" * 80)
    print(f"Porta: {MODBUS_CONFIG['port']}")
    print(f"Baudrate: {MODBUS_CONFIG['baudrate']}")
    print(f"Timeout: {MODBUS_CONFIG['timeout']}s")
    configured_slave_id = MODBUS_CONFIG.get("slave_id", 1)
    print(f"Slave ID configurato: {configured_slave_id}")
    print("=" * 80)
    print()
    
    # Crea il reader
    reader = RSProReader(
        port=MODBUS_CONFIG["port"],
        baudrate=MODBUS_CONFIG["baudrate"],
        timeout=MODBUS_CONFIG["timeout"]
    )
    
    # Connetti
    print("Tentativo di connessione...")
    if not reader.connect():
        print("❌ ERRORE: Impossibile connettersi al dispositivo Modbus")
        print(f"   Verifica che la porta {MODBUS_CONFIG['port']} sia corretta")
        return False
    
    print("✅ Connessione riuscita!")
    print()
    
    # Delay dopo connessione
    post_connect_delay = MODBUS_CONFIG.get("post_connect_delay", 0.5)
    if post_connect_delay > 0:
        print(f"Attesa {post_connect_delay}s per stabilizzare...")
        time.sleep(post_connect_delay)
        print()
    
    try:
        # Test 0: Trova slave ID corretto
        print("\n" + "="*80)
        print("TEST 0: Ricerca Slave ID corretto")
        print("="*80)
        responding_slaves = test_slave_ids(reader)
        
        # Determina quale slave ID usare
        if responding_slaves:
            slave_id, _ = responding_slaves[0]
            print(f"✅ Usando slave ID {slave_id} per i test successivi\n")
        else:
            slave_id = configured_slave_id
            print(f"⚠️  Nessuno slave ID ha risposto, uso quello configurato: {slave_id}\n")
            print("   I test successivi potrebbero fallire se lo slave ID è errato.\n")
        
        # Test 1: Registri specifici comuni
        print("\n" + "="*80)
        print(f"TEST 1: Registri specifici comuni (Slave ID {slave_id})")
        print("="*80)
        specific_results = test_specific_registers(reader, slave_id)
        
        # Test 2: Scan range iniziale (0-100)
        print("\n" + "="*80)
        print(f"TEST 2: Scan registri 0-100 (per trovare potenza, tensione, etc.) - Slave ID {slave_id}")
        print("="*80)
        range1_results = test_register_range(reader, 0, 100, slave_id, step=2)
        
        # Test 3: Scan range energia (40-80)
        print("\n" + "="*80)
        print(f"TEST 3: Scan registri 40-80 (tipicamente energia) - Slave ID {slave_id}")
        print("="*80)
        range2_results = test_register_range(reader, 40, 80, slave_id, step=2)
        
        # Riepilogo
        print("\n" + "="*80)
        print("RIEPILOGO VALORI TROVATI")
        print("="*80)
        
        all_results = specific_results + range1_results + range2_results
        
        # Raggruppa per tipo
        by_type = {}
        for item in all_results:
            if len(item) == 5:  # specific_results
                reg, modbus_addr, desc, value, raw = item
                key = desc
            else:  # range_results
                reg, modbus_addr, value, desc, raw = item
                key = desc
            
            if key not in by_type:
                by_type[key] = []
            by_type[key].append((reg, modbus_addr, value, raw))
        
        for value_type, items in sorted(by_type.items()):
            print(f"\n{value_type}:")
            for reg, modbus_addr, value, raw in items:
                print(f"  Registro {reg:04X} (Modbus {modbus_addr:05d}): {value:12.4f} "
                      f"[Raw: {raw[0]:04X} {raw[1]:04X}]")
        
        print("\n" + "="*80)
        print("SUGGERIMENTI:")
        print("="*80)
        print("1. Cerca valori di potenza plausibili (0-100000W)")
        print("2. Cerca valori di tensione plausibili (0-500V)")
        print("3. Cerca valori di energia plausibili (0-1000000kWh)")
        print("4. Confronta i valori con quelli visualizzati sul display del RS-PRO")
        print("5. I registri trovati possono essere usati per aggiornare rspro.py")
        print()
        
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnetti
        reader.disconnect()
        print("Connessione chiusa")
    
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
