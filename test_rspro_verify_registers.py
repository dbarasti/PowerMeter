#!/usr/bin/env python3
"""
Script per verificare i registri di potenza ed energia del RS-PRO.
Legge i registri e mostra i valori per verificare che siano corretti.
"""
import sys
import time
from pathlib import Path

# Aggiungi il path dell'app al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from app.config import MODBUS_CONFIG
from app.modbus.rspro import RSProReader

def main():
    """Test dei registri di potenza ed energia."""
    print("=" * 80)
    print("Test Registri Potenza ed Energia RS-PRO")
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
    
    slave_id = MODBUS_CONFIG.get("slave_id", 1)
    
    # Test Phase 1 (Heater)
    print("=" * 80)
    print("FASE 1 (Stufa/Heater)")
    print("=" * 80)
    print()
    
    print(f"Registro Tensione: 0x{reader.REGISTER_PHASE1_VOLTAGE:04X} (Modbus {30001 + reader.REGISTER_PHASE1_VOLTAGE})")
    voltage1 = reader.read_voltage(phase=1, slave_id=slave_id)
    print(f"  Tensione: {voltage1}V" if voltage1 is not None else "  Tensione: ERRORE")
    print()
    
    print(f"Registro Corrente: 0x{reader.REGISTER_PHASE1_CURRENT:04X} (Modbus {30001 + reader.REGISTER_PHASE1_CURRENT})")
    current1 = reader.read_current(phase=1, slave_id=slave_id)
    print(f"  Corrente: {current1}A" if current1 is not None else "  Corrente: ERRORE")
    print()
    
    print(f"Registro Potenza: 0x{reader.REGISTER_PHASE1_POWER:04X} (Modbus {30001 + reader.REGISTER_PHASE1_POWER})")
    power1 = reader.read_power(phase=1, slave_id=slave_id)
    print(f"  Potenza: {power1}W" if power1 is not None else "  Potenza: ERRORE")
    if power1 is not None:
        print(f"  Potenza plausibile: {'✅' if 0 <= power1 <= 100000 else '❌'}")
    print()
    
    print(f"Registro Energia: 0x{reader.REGISTER_PHASE1_ENERGY:04X} (Modbus {30001 + reader.REGISTER_PHASE1_ENERGY})")
    energy1 = reader.read_energy(phase=1, slave_id=slave_id)
    print(f"  Energia: {energy1}kWh" if energy1 is not None else "  Energia: ERRORE")
    if energy1 is not None:
        print(f"  Energia plausibile: {'✅' if 0 <= energy1 <= 1000000 else '❌'}")
    print()
    
    time.sleep(0.5)
    
    # Test Phase 2 (Fan)
    print("=" * 80)
    print("FASE 2 (Ventilatore/Fan)")
    print("=" * 80)
    print()
    
    print(f"Registro Tensione: 0x{reader.REGISTER_PHASE2_VOLTAGE:04X} (Modbus {30001 + reader.REGISTER_PHASE2_VOLTAGE})")
    voltage2 = reader.read_voltage(phase=2, slave_id=slave_id)
    print(f"  Tensione: {voltage2}V" if voltage2 is not None else "  Tensione: ERRORE")
    print()
    
    print(f"Registro Corrente: 0x{reader.REGISTER_PHASE2_CURRENT:04X} (Modbus {30001 + reader.REGISTER_PHASE2_CURRENT})")
    current2 = reader.read_current(phase=2, slave_id=slave_id)
    print(f"  Corrente: {current2}A" if current2 is not None else "  Corrente: ERRORE")
    print()
    
    print(f"Registro Potenza: 0x{reader.REGISTER_PHASE2_POWER:04X} (Modbus {30001 + reader.REGISTER_PHASE2_POWER})")
    power2 = reader.read_power(phase=2, slave_id=slave_id)
    print(f"  Potenza: {power2}W" if power2 is not None else "  Potenza: ERRORE")
    if power2 is not None:
        print(f"  Potenza plausibile: {'✅' if 0 <= power2 <= 100000 else '❌'}")
    print()
    
    print(f"Registro Energia: 0x{reader.REGISTER_PHASE2_ENERGY:04X} (Modbus {30001 + reader.REGISTER_PHASE2_ENERGY})")
    energy2 = reader.read_energy(phase=2, slave_id=slave_id)
    print(f"  Energia: {energy2}kWh" if energy2 is not None else "  Energia: ERRORE")
    if energy2 is not None:
        print(f"  Energia plausibile: {'✅' if 0 <= energy2 <= 1000000 else '❌'}")
    print()
    
    # Test lettura completa
    print("=" * 80)
    print("Lettura Completa (read_all)")
    print("=" * 80)
    print()
    
    print("Fase 1:")
    data1 = reader.read_all(phase=1, slave_id=slave_id)
    if data1:
        print(f"  Tensione: {data1.get('voltage_v')}V")
        print(f"  Corrente: {data1.get('current_a')}A")
        print(f"  Potenza: {data1.get('power_w')}W")
        print(f"  Energia: {data1.get('energy_kwh')}kWh")
    else:
        print("  ERRORE: Nessun dato")
    print()
    
    print("Fase 2:")
    data2 = reader.read_all(phase=2, slave_id=slave_id)
    if data2:
        print(f"  Tensione: {data2.get('voltage_v')}V")
        print(f"  Corrente: {data2.get('current_a')}A")
        print(f"  Potenza: {data2.get('power_w')}W")
        print(f"  Energia: {data2.get('energy_kwh')}kWh")
    else:
        print("  ERRORE: Nessun dato")
    print()
    
    # Verifica coerenza
    print("=" * 80)
    print("Verifica Coerenza")
    print("=" * 80)
    print()
    
    if power1 is not None and power2 is not None:
        total_power = power1 + power2
        print(f"Potenza totale (Fase 1 + Fase 2): {total_power}W")
        
        # Leggi potenza totale dal sistema
        total_system_power = reader._read_float_register(
            reader.REGISTER_TOTAL_POWER, 0, slave_id
        )
        if total_system_power is not None:
            print(f"Potenza totale sistema (registro 0x{reader.REGISTER_TOTAL_POWER:04X}): {total_system_power}W")
            diff = abs(total_power - total_system_power)
            print(f"Differenza: {diff}W ({'✅ Coerente' if diff < 100 else '⚠️  Non coerente'})")
    print()
    
    reader.disconnect()
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
