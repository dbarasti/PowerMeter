#!/usr/bin/env python3
"""
Script di test per verificare la comunicazione Modbus RTU con daisy chain.
Legge un registro da entrambi i dispositivi RS-PRO.
"""
import sys
import time
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

def test_modbus_daisy():
    """Test semplice di lettura da entrambi i dispositivi."""
    print("=" * 60)
    print("Test Modbus RTU Daisy Chain")
    print("=" * 60)
    print(f"Porta: {MODBUS_CONFIG['port']}")
    print(f"Baudrate: {MODBUS_CONFIG['baudrate']}")
    print(f"Timeout: {MODBUS_CONFIG['timeout']}s")
    print(f"Slave IDs: Heater={MODBUS_CONFIG['slave_ids']['heater']}, Fan={MODBUS_CONFIG['slave_ids']['fan']}")
    print("=" * 60)
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
    
    # Test lettura da HEATER (slave ID 1)
    heater_id = MODBUS_CONFIG["slave_ids"]["heater"]
    print(f"📡 Lettura da HEATER (Slave ID {heater_id})...")
    print("-" * 60)
    
    try:
        # Nota: RS-PRO non ha tensione documentata nel PDF, quindi saltiamo questo test
        # Prova a leggere la potenza
        print(f"  → Tentativo lettura potenza da slave {heater_id}...")
        power = reader.read_power(heater_id)
        if power is not None:
            print(f"✅ Potenza HEATER: {power:.2f} W")
        else:
            print("❌ ERRORE: Impossibile leggere potenza da HEATER")
        
        # Prova a leggere l'energia
        print(f"  → Tentativo lettura energia da slave {heater_id}...")
        energy = reader.read_energy(heater_id)
        if energy is not None:
            print(f"✅ Energia HEATER: {energy:.4f} kWh")
        else:
            print("❌ ERRORE: Impossibile leggere energia da HEATER")
            
    except Exception as e:
        print(f"❌ ECCEZIONE durante lettura HEATER: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Delay tra richieste
    inter_request_delay = MODBUS_CONFIG.get("inter_request_delay", 0.2)
    if inter_request_delay > 0:
        print(f"Attesa {inter_request_delay}s prima di leggere FAN...")
        time.sleep(inter_request_delay)
        print()
    
    # Test lettura da FAN (slave ID 2)
    fan_id = MODBUS_CONFIG["slave_ids"]["fan"]
    print(f"📡 Lettura da FAN (Slave ID {fan_id})...")
    print("-" * 60)
    print(f"⚠️  NOTA: Se solo HEATER è collegato, questa lettura DOVREBBE fallire")
    print()
    
    try:
        # Test diretto con pymodbus per vedere la risposta raw
        print(f"  → Test diretto lettura registro da slave {fan_id}...")
        try:
            # RS-PRO usa registro 0x0034 per la potenza (non 0x0000)
            result = reader.client.read_input_registers(0x0034, 2, unit=fan_id)
            if result.isError():
                print(f"   ✅ RISPOSTA ERRORE (comportamento corretto): {result}")
            else:
                print(f"   ⚠️  RISPOSTA VALIDA (inatteso se FAN non collegato):")
                print(f"      Registri: {result.registers}")
                print(f"      Questo significa che qualcosa ha risposto a slave ID {fan_id}!")
        except Exception as e:
            print(f"   ✅ ECCEZIONE durante lettura (comportamento atteso): {type(e).__name__}: {e}")
        
        print()
        
        # Nota: RS-PRO non ha tensione documentata nel PDF, quindi saltiamo questo test
        # Prova a leggere la potenza
        print(f"  → Tentativo lettura potenza da slave {fan_id}...")
        power = reader.read_power(fan_id)
        if power is not None:
            print(f"✅ Potenza FAN: {power:.2f} W")
            print(f"   ⚠️  ATTENZIONE: Lettura riuscita anche se FAN non è collegato!")
        else:
            print("❌ ERRORE: Impossibile leggere potenza da FAN (comportamento atteso se non collegato)")
        
        # Prova a leggere l'energia
        print(f"  → Tentativo lettura energia da slave {fan_id}...")
        energy = reader.read_energy(fan_id)
        if energy is not None:
            print(f"✅ Energia FAN: {energy:.4f} kWh")
            print(f"   ⚠️  ATTENZIONE: Lettura riuscita anche se FAN non è collegato!")
        else:
            print("❌ ERRORE: Impossibile leggere energia da FAN (comportamento atteso se non collegato)")
            
    except Exception as e:
        print(f"❌ ECCEZIONE durante lettura FAN: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Test Slave ID - Verifica quale dispositivo risponde")
    print("=" * 60)
    print("Verificando quale slave ID risponde effettivamente...")
    print()
    
    # Test: prova a leggere da diversi slave ID per vedere quale risponde
    # Includiamo anche 9 perché dai log vediamo che il dispositivo risponde con 0x9
    responding_slaves = []
    for test_id in [1, 2, 3, 9, 247]:  # 9 sembra essere lo slave ID configurato, 247 è broadcast
        try:
            print(f"  → Test slave ID {test_id}...", end=" ")
            # RS-PRO usa registro 0x0034 per la potenza
            result = reader.client.read_input_registers(0x0034, 2, unit=test_id)
            if not result.isError():
                # Verifica se la risposta contiene dati validi
                if len(result.registers) == 2:
                    responding_slaves.append(test_id)
                    print(f"✅ RISPOSTA (registri: {result.registers})")
                else:
                    print(f"⚠️  Risposta ma dati anomali")
            else:
                print(f"❌ Errore: {result}")
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}")
        
        time.sleep(0.1)
    
    print()
    if responding_slaves:
        print(f"⚠️  ATTENZIONE: I seguenti slave ID rispondono: {responding_slaves}")
        print()
        # Verifica quale slave ID è nella risposta effettiva
        print("Analisi risposte Modbus:")
        for test_id in responding_slaves:
            try:
                # RS-PRO usa registro 0x0034 per la potenza
                result = reader.client.read_input_registers(0x0034, 2, unit=test_id)
                if not result.isError():
                    # Estrai lo slave ID dalla risposta (primo byte del frame raw)
                    # Nota: pymodbus potrebbe non esporre direttamente lo slave ID nella risposta
                    print(f"   Slave ID {test_id}: Risposta ricevuta (registri: {result.registers})")
            except:
                pass
        
        print()
        print("🔍 DIAGNOSI:")
        print("   Il dispositivo risponde a più slave ID, il che è ANOMALO.")
        print("   Nei log Modbus vediamo che le risposte hanno sempre slave ID 0x9 (9).")
        print()
        print("💡 SOLUZIONE:")
        print("   1. Il dispositivo HEATER ha slave ID 9 configurato (non 1)")
        print("   2. Configura il dispositivo HEATER con slave ID = 1")
        print("   3. Configura il dispositivo FAN con slave ID = 2")
        print("   4. Usa il software di configurazione RS-PRO o")
        print("      scrivi il registro holding per lo slave ID (vedi manuale RS-PRO)")
    else:
        print("✅ Nessun slave ID ha risposto (comportamento atteso se nessun dispositivo collegato)")
    
    print()
    print("=" * 60)
    print("Test completato")
    print("=" * 60)
    
    # Disconnetti
    reader.disconnect()
    print("Connessione chiusa")
    
    return True


if __name__ == "__main__":
    try:
        test_modbus_daisy()
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

