#!/usr/bin/env python3
"""
Script per trovare il registro corretto della potenza istantanea Fase 1.
Cerca un valore tra 900-1000W.
"""
import sys
import time
from pathlib import Path

# Aggiungi il path dell'app al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from app.config import MODBUS_CONFIG
from app.modbus.rspro import RSProReader

def scan_registers_for_power(reader, start_reg: int = 0, end_reg: int = 0x0050, slave_id: int = 1):
    """
    Scansiona registri per trovare valori di potenza plausibili (900-1000W).
    """
    print("=" * 80)
    print("Scansione Registri per Potenza Fase 1 (900-1000W)")
    print("=" * 80)
    print()
    print(f"Scansione da registro 0x{start_reg:04X} a 0x{end_reg:04X}")
    print()
    
    found_values = []
    
    for reg in range(start_reg, end_reg + 1, 2):  # Solo offset pari (float = 2 registri)
        try:
            value = reader._read_float_register(reg, 1, slave_id)
            
            if value is not None:
                modbus_addr = 30001 + reg
                
                # Cerca valori tra 900-1000W (con un po' di tolleranza)
                if 800 <= value <= 1100:
                    status = "🎯 TROVATO!"
                    found_values.append((reg, modbus_addr, value))
                elif 0 <= value <= 100000:
                    status = "✅ Plausibile"
                else:
                    status = "⚠️  Anomalo"
                
                print(f"{status} Reg 0x{reg:04X} (Modbus {modbus_addr:05d}): {value:12.4f} W")
            
            time.sleep(0.05)  # Piccolo delay tra letture
            
        except Exception as e:
            # Ignora errori e continua
            pass
    
    print()
    print("=" * 80)
    if found_values:
        print("🎯 REGISTRI TROVATI CON VALORE 900-1000W:")
        print("=" * 80)
        for reg, modbus_addr, value in found_values:
            print(f"  Offset: 0x{reg:04X} ({reg})")
            print(f"  Modbus: {modbus_addr} ({modbus_addr-30001})")
            print(f"  Valore: {value:.2f} W")
            print()
    else:
        print("❌ Nessun registro trovato con valore tra 900-1000W")
        print("   Prova ad aumentare il range di scansione o verifica che la stufa sia accesa")
    
    return found_values

def test_specific_power_registers(reader, slave_id: int = 1):
    """
    Testa registri specifici comuni per la potenza.
    """
    print("=" * 80)
    print("Test Registri Specifici Potenza")
    print("=" * 80)
    print()
    
    # Registri da testare (basati sulla documentazione e varianti comuni)
    test_registers = [
        (0x000C, "Phase 1 Active Power (doc)"),
        (0x000D, "Phase 1 Active Power +1"),
        (0x000E, "Phase 2 Active Power (doc)"),
        (0x000A, "Phase 1 Active Power -2"),
        (0x0010, "Phase 1 Active Power +4"),
        (0x0012, "Phase 1 Apparent Power (doc)"),
        (0x0014, "Phase 1 Apparent Power +2"),
        (0x0016, "Phase 1 Apparent Power +4"),
        (0x0018, "Phase 1 Energy (doc)"),
        (0x001A, "Phase 2 Energy (doc)"),
        (0x001C, "Phase 3 Energy (doc)"),
        (0x0020, "Altro registro energia"),
        (0x0022, "Altro registro energia +2"),
        (0x0034, "Total System Power (doc)"),
        (0x0036, "Total System Power +2"),
    ]
    
    found = []
    
    for reg, description in test_registers:
        try:
            value = reader._read_float_register(reg, 1, slave_id)
            modbus_addr = 30001 + reg
            
            if value is not None:
                if 800 <= value <= 1100:
                    status = "🎯 TROVATO!"
                    found.append((reg, modbus_addr, value, description))
                elif 0 <= value <= 100000:
                    status = "✅"
                else:
                    status = "⚠️"
                
                print(f"{status} 0x{reg:04X} (Modbus {modbus_addr:05d}): {description:40s} = {value:12.4f} W")
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"❌ 0x{reg:04X}: {description:40s} = ERRORE: {e}")
    
    print()
    if found:
        print("=" * 80)
        print("🎯 REGISTRI TROVATI:")
        print("=" * 80)
        for reg, modbus_addr, value, desc in found:
            print(f"  {desc}")
            print(f"  Offset: 0x{reg:04X} ({reg})")
            print(f"  Modbus: {modbus_addr} ({modbus_addr-30001})")
            print(f"  Valore: {value:.2f} W")
            print()
    
    return found

def main():
    """Main function."""
    print("=" * 80)
    print("Ricerca Registro Potenza Fase 1 (900-1000W)")
    print("=" * 80)
    print()
    
    # Crea reader
    reader = RSProReader(
        port=MODBUS_CONFIG["port"],
        baudrate=MODBUS_CONFIG["baudrate"],
        timeout=MODBUS_CONFIG.get("timeout", 1.0)
    )
    
    if not reader.connect():
        print("❌ Impossibile connettersi al dispositivo")
        return 1
    
    print("✅ Connesso al dispositivo RS-PRO")
    print()
    print("⚠️  ASSICURATI CHE LA STUFA SIA ACCESA (900-1000W)")
    print()
    time.sleep(1)
    
    slave_id = MODBUS_CONFIG.get("slave_id", 1)
    
    # Test 1: Registri specifici
    found1 = test_specific_power_registers(reader, slave_id)
    
    time.sleep(0.5)
    
    # Test 2: Scansione completa
    print()
    print("=" * 80)
    print("Scansione Completa Registri")
    print("=" * 80)
    print()
    found2 = scan_registers_for_power(reader, start_reg=0, end_reg=0x0050, slave_id=slave_id)
    
    # Riepilogo
    print()
    print("=" * 80)
    print("RIEPILOGO")
    print("=" * 80)
    print()
    
    all_found = found1 + found2
    
    if all_found:
        print("🎯 REGISTRI CANDIDATI PER POTENZA FASE 1:")
        for item in all_found:
            if len(item) == 4:
                reg, modbus_addr, value, desc = item
                print(f"  - {desc}: 0x{reg:04X} (Modbus {modbus_addr}) = {value:.2f}W")
            else:
                reg, modbus_addr, value = item
                print(f"  - 0x{reg:04X} (Modbus {modbus_addr}) = {value:.2f}W")
    else:
        print("❌ Nessun registro trovato con valore 900-1000W")
        print("   Verifica che:")
        print("   1. La stufa sia accesa e consumi 900-1000W")
        print("   2. Il dispositivo sia connesso correttamente")
        print("   3. Lo slave ID sia corretto")
    
    reader.disconnect()
    print()
    print("✅ Test completato")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
