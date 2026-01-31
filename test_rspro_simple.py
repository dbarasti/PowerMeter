#!/usr/bin/env python3
"""
Script minimale per testare comunicazione Modbus RS-PRO.
Non usa nulla del progetto, solo pymodbus.
"""
import sys
import struct
import time

try:
    # pymodbus 3.x
    from pymodbus.client import ModbusSerialClient
    from pymodbus import Framer
    PYMODBUS_3X = True
    print("Usando pymodbus 3.x")
except ImportError:
    # pymodbus 2.x fallback
    from pymodbus.client.sync import ModbusSerialClient
    PYMODBUS_3X = False
    print("Usando pymodbus 2.x")

from pymodbus.exceptions import ModbusException


def test_simple_read():
    """Test semplice di lettura Modbus."""
    
    # Configurazione - MODIFICA QUESTI VALORI
    PORT = "/dev/cu.usbserial-BG01Q45C"  # Cambia con la tua porta
    BAUDRATE = 9600
    SLAVE_ID = 1
    TIMEOUT = 3.0  # Aumentato a 3 secondi
    
    print("=" * 60)
    print("Test Modbus RS-PRO - Script Minimale")
    print("=" * 60)
    print(f"Porta: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Slave ID: {SLAVE_ID}")
    print(f"Timeout: {TIMEOUT}s")
    print("=" * 60)
    print()
    
    # Crea client
    print("Creazione client Modbus...")
    try:
        if PYMODBUS_3X:
            client = ModbusSerialClient(
                port=PORT,
                framer=Framer.RTU,
                baudrate=BAUDRATE,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=TIMEOUT,
            )
            result = client.connect()
            if result is not None and not result:
                print("❌ ERRORE: Impossibile connettersi alla porta seriale")
                return False
        else:
            client = ModbusSerialClient(
                method="rtu",
                port=PORT,
                baudrate=BAUDRATE,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=TIMEOUT,
            )
            if not client.connect():
                print("❌ ERRORE: Impossibile connettersi alla porta seriale")
                return False
        
        print("✅ Connessione seriale stabilita")
        print()
        
        # Delay dopo connessione
        print("Attesa 1 secondo per stabilizzare...")
        time.sleep(1.0)
        print()
        
        # Prova a pulire il buffer seriale
        print("Pulizia buffer seriale...")
        try:
            if hasattr(client, 'socket') and client.socket:
                if hasattr(client.socket, 'reset_input_buffer'):
                    client.socket.reset_input_buffer()
                elif hasattr(client.socket, 'flushInput'):
                    client.socket.flushInput()
            elif hasattr(client, 'serial') and client.serial:
                if hasattr(client.serial, 'reset_input_buffer'):
                    client.serial.reset_input_buffer()
                elif hasattr(client.serial, 'flushInput'):
                    client.serial.flushInput()
            print("✅ Buffer pulito")
        except Exception as e:
            print(f"⚠️  Impossibile pulire buffer: {e}")
        print()
        
        # Test 1: Leggi registro 0 (Phase 1 Voltage) - 2 registri
        print("Test 1: Lettura Phase 1 Voltage (registro 0, 2 registri)")
        print("-" * 60)
        print(f"Invio richiesta: read_input_registers(0, 2, unit={SLAVE_ID})")
        print("⚠️  ATTENZIONE: Guarda il LED TX sul convertitore USB-RS485")
        print("⚠️  ATTENZIONE: Guarda il simbolo di scambio dati sul power meter")
        
        start_time = time.time()
        try:
            # Prova con timeout più lungo
            result = client.read_input_registers(0, 2, unit=SLAVE_ID)
            elapsed = time.time() - start_time
            
            print(f"Tempo trascorso: {elapsed:.3f}s")
            
            if result.isError():
                print(f"❌ ERRORE nella risposta: {result}")
                error_msg = str(result)
                if hasattr(result, 'message'):
                    error_msg = result.message
                print(f"   Messaggio: {error_msg}")
                print()
                print("🔍 DIAGNOSI:")
                print("   - TX LED si accende → Trasmissione OK")
                print("   - Power meter mostra simbolo → Riceve la richiesta")
                print("   - Nessuna risposta ricevuta → Problema di ricezione")
                print()
                print("💡 POSSIBILI CAUSE:")
                print("   1. Cablaggio RS485 invertito (A/B scambiati)")
                print("   2. Problema con il buffer seriale")
                print("   3. Slave ID errato (prova altri ID)")
                print("   4. Timeout troppo breve (già aumentato a 3s)")
                print()
                print("🔧 PROVA:")
                print("   - Inverti i fili A e B sul convertitore USB-RS485")
                print("   - Verifica lo slave ID sul display del power meter")
                print("   - Prova con slave ID diversi (1, 2, 3, 9, 10)")
            else:
                print("✅ RISPOSTA RICEVUTA!")
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
                    value_bytes = struct.pack('>HH', low_word, high_word)
                    value = struct.unpack('>f', value_bytes)[0]
                    print(f"   Valore: {value:.2f} V")
                    
                    if 0.0 <= value <= 500.0:
                        print(f"   ✅ Valore plausibile: {value:.2f} V")
                    else:
                        print(f"   ⚠️  Valore non plausibile: {value:.2f} V")
        
        except ModbusException as e:
            print(f"❌ ModbusException: {type(e).__name__}: {e}")
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        time.sleep(1.0)  # Delay più lungo tra letture
        
        # Test 2: Prova diversi slave ID
        print("Test 2: Prova diversi Slave ID")
        print("-" * 60)
        print("Provo slave ID: 1, 2, 3, 9, 10")
        print()
        
        for test_slave_id in [1, 2, 3, 9, 10]:
            print(f"  → Test slave ID {test_slave_id}...", end=" ", flush=True)
            try:
                # Pulisci buffer prima di ogni tentativo
                if hasattr(client, 'socket') and client.socket:
                    if hasattr(client.socket, 'reset_input_buffer'):
                        client.socket.reset_input_buffer()
                elif hasattr(client, 'serial') and client.serial:
                    if hasattr(client.serial, 'reset_input_buffer'):
                        client.serial.reset_input_buffer()
                
                time.sleep(0.2)  # Piccolo delay
                
                result = client.read_input_registers(0, 2, unit=test_slave_id)
                
                if result.isError():
                    print("❌ Errore")
                else:
                    print(f"✅ RISPOSTA! Registri: {result.registers}")
                    if len(result.registers) == 2:
                        # IMPORTANTE: RS-PRO invia registri in ordine Little-Endian
                        low = result.registers[0]
                        high = result.registers[1]
                        value_bytes = struct.pack('>HH', low, high)
                        value = struct.unpack('>f', value_bytes)[0]
                        print(f"      Valore: {value:.2f} V")
            except Exception as e:
                print(f"❌ Eccezione: {type(e).__name__}")
            
            time.sleep(0.3)
        
        print()
        time.sleep(1.0)
        
        # Test 3: Leggi registro 12 (Phase 1 Power) - 2 registri
        print("Test 3: Lettura Phase 1 Power (registro 12, 2 registri)")
        print("-" * 60)
        print(f"Invio richiesta: read_input_registers(12, 2, unit={SLAVE_ID})")
        
        start_time = time.time()
        try:
            # Pulisci buffer
            if hasattr(client, 'socket') and client.socket:
                if hasattr(client.socket, 'reset_input_buffer'):
                    client.socket.reset_input_buffer()
            elif hasattr(client, 'serial') and client.serial:
                if hasattr(client.serial, 'reset_input_buffer'):
                    client.serial.reset_input_buffer()
            
            time.sleep(0.2)
            
            result = client.read_input_registers(12, 2, unit=SLAVE_ID)
            elapsed = time.time() - start_time
            
            print(f"Tempo trascorso: {elapsed:.3f}s")
            
            if result.isError():
                print(f"❌ ERRORE nella risposta: {result}")
            else:
                print("✅ RISPOSTA RICEVUTA!")
                print(f"   Registri: {result.registers}")
                
                if len(result.registers) == 2:
                    # IMPORTANTE: RS-PRO invia registri in ordine Little-Endian
                    low_word = result.registers[0]
                    high_word = result.registers[1]
                    
                    # Interpreta in Little-Endian (low, high)
                    value_bytes = struct.pack('>HH', low_word, high_word)
                    value = struct.unpack('>f', value_bytes)[0]
                    print(f"   Valore: {value:.2f} W")
                    
                    if 0.0 <= value <= 100000.0:
                        print(f"   ✅ Valore plausibile: {value:.2f} W")
                    else:
                        print(f"   ⚠️  Valore non plausibile: {value:.2f} W")
        
        except Exception as e:
            print(f"❌ Eccezione: {type(e).__name__}: {e}")
        
        print()
        
        # Chiudi connessione
        client.close()
        print("✅ Test completato")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        test_simple_read()
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
