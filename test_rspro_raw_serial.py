#!/usr/bin/env python3
"""
Test con comunicazione seriale raw (senza pymodbus) per diagnosticare il problema.
"""
import serial
import time
import struct

# Configurazione
PORT = "/dev/cu.usbserial-BG01Q45C"
BAUDRATE = 9600
TIMEOUT = 3.0
SLAVE_ID = 1

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
    """Costruisce un frame Modbus RTU."""
    # Frame: [Slave ID, Function, Start Addr High, Start Addr Low, 
    #         Num Reg High, Num Reg Low, CRC Low, CRC High]
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
    """Analizza la risposta Modbus."""
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

def test_raw_serial():
    """Test con comunicazione seriale raw."""
    print("=" * 60)
    print("Test Modbus RS-PRO - Comunicazione Serial Raw")
    print("=" * 60)
    print(f"Porta: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Slave ID: {SLAVE_ID}")
    print(f"Timeout: {TIMEOUT}s")
    print("=" * 60)
    print()
    
    try:
        # Apri porta seriale
        print("Apertura porta seriale...")
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=TIMEOUT
        )
        print("✅ Porta seriale aperta")
        print()
        
        # Pulisci buffer
        print("Pulizia buffer...")
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.5)
        print("✅ Buffer pulito")
        print()
        
        # Costruisci richiesta Modbus: Read Input Registers (Function 04)
        # Registro 0, 2 registri
        print("Test 1: Read Input Registers - Registro 0, 2 registri")
        print("-" * 60)
        
        request = build_modbus_read_request(SLAVE_ID, 0x04, 0, 2)
        print(f"Richiesta (hex): {' '.join(f'{b:02X}' for b in request)}")
        print(f"   Slave ID: {request[0]}")
        print(f"   Function: {request[1]:02X} (Read Input Registers)")
        print(f"   Start Addr: {(request[2] << 8) | request[3]}")
        print(f"   Num Reg: {(request[4] << 8) | request[5]}")
        print(f"   CRC: {request[6]:02X} {request[7]:02X}")
        print()
        
        print("⚠️  ATTENZIONE: Guarda il LED TX sul convertitore")
        print("⚠️  ATTENZIONE: Guarda il simbolo sul power meter")
        print()
        
        # Invia richiesta
        print("Invio richiesta...")
        ser.write(request)
        ser.flush()
        print("✅ Richiesta inviata")
        print()
        
        # Attendi risposta
        print("Attesa risposta (timeout 3s)...")
        start_time = time.time()
        
        # Leggi risposta
        response = b''
        while True:
            if time.time() - start_time > TIMEOUT:
                print("⏱️  TIMEOUT - Nessuna risposta ricevuta")
                break
            
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                response += chunk
                print(f"   Ricevuti {len(chunk)} bytes (totale: {len(response)} bytes)")
                
                # Se abbiamo almeno 4 bytes, potrebbe essere una risposta completa
                if len(response) >= 4:
                    # Verifica se è una risposta completa
                    if response[1] == 0x04:  # Function code
                        byte_count = response[2]
                        expected_len = 3 + byte_count + 2  # header + data + CRC
                        if len(response) >= expected_len:
                            print(f"   ✅ Risposta completa ricevuta ({len(response)} bytes)")
                            break
                    elif response[1] == 0x84:  # Exception (0x04 | 0x80)
                        print(f"   ⚠️  Exception response ricevuta")
                        break
            
            time.sleep(0.01)  # Piccolo delay
        
        elapsed = time.time() - start_time
        print(f"Tempo trascorso: {elapsed:.3f}s")
        print()
        
        if len(response) == 0:
            print("❌ NESSUN DATO RICEVUTO")
            print()
            print("🔍 DIAGNOSI:")
            print("   - TX LED si accende → Trasmissione OK")
            print("   - Power meter mostra simbolo → Riceve la richiesta")
            print("   - Nessun dato ricevuto → Problema di ricezione")
            print()
            print("💡 POSSIBILI CAUSE:")
            print("   1. ⚠️  CABLAGGIO RS485 INVERTITO (A/B scambiati)")
            print("      → Prova a invertire i fili A e B sul convertitore USB-RS485")
            print("   2. Slave ID errato")
            print("      → Verifica lo slave ID sul display del power meter")
            print("   3. Problema con il convertitore USB-RS485")
            print("      → Prova un altro convertitore se disponibile")
            print("   4. Terminazioni RS485 mancanti")
            print("      → Se il cavo è lungo, potrebbero servire resistenze 120 ohm")
        else:
            print(f"✅ DATI RICEVUTI: {len(response)} bytes")
            print(f"   Raw (hex): {' '.join(f'{b:02X}' for b in response)}")
            print()
            
            # Analizza risposta
            registers, error = parse_modbus_response(response, SLAVE_ID, 0x04)
            
            if error:
                print(f"❌ Errore parsing: {error}")
            else:
                print(f"✅ RISPOSTA VALIDA!")
                print(f"   Registri: {registers}")
                
                if len(registers) == 2:
                    high_word = registers[0]
                    low_word = registers[1]
                    print(f"   Registro 0: {high_word} (0x{high_word:04X})")
                    print(f"   Registro 1: {low_word} (0x{low_word:04X})")
                    print()
                    
                    # Prova tutte le combinazioni possibili
                    print("   Tentativo interpretazione valori:")
                    print()
                    
                    # 1. Big-Endian standard (high_word, low_word)
                    value_bytes = struct.pack('>HH', high_word, low_word)
                    value_be = struct.unpack('>f', value_bytes)[0]
                    print(f"   1. BE (reg0, reg1): {value_be:.4f} V", end="")
                    if 0.0 <= value_be <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # 2. Little-Endian registri (low_word, high_word)
                    value_bytes_le = struct.pack('>HH', low_word, high_word)
                    value_le = struct.unpack('>f', value_bytes_le)[0]
                    print(f"   2. LE (reg1, reg0): {value_le:.4f} V", end="")
                    if 0.0 <= value_le <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # 3. Big-Endian con byte invertiti nei registri
                    high_swapped = ((high_word & 0xFF) << 8) | ((high_word >> 8) & 0xFF)
                    low_swapped = ((low_word & 0xFF) << 8) | ((low_word >> 8) & 0xFF)
                    value_bytes_sw = struct.pack('>HH', high_swapped, low_swapped)
                    value_sw = struct.unpack('>f', value_bytes_sw)[0]
                    print(f"   3. BE byte-swapped: {value_sw:.4f} V", end="")
                    if 0.0 <= value_sw <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # 4. Little-Endian completo
                    value_bytes_le_full = struct.pack('<HH', high_word, low_word)
                    value_le_full = struct.unpack('<f', value_bytes_le_full)[0]
                    print(f"   4. LE completo: {value_le_full:.4f} V", end="")
                    if 0.0 <= value_le_full <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # 5. Interpreta i byte raw direttamente
                    raw_bytes = response[3:7]  # I 4 byte di dati
                    print(f"   Raw bytes: {' '.join(f'{b:02X}' for b in raw_bytes)}")
                    
                    # Big-Endian
                    value_raw_be = struct.unpack('>f', raw_bytes)[0]
                    print(f"   5. Raw BE: {value_raw_be:.4f} V", end="")
                    if 0.0 <= value_raw_be <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # Little-Endian
                    value_raw_le = struct.unpack('<f', raw_bytes)[0]
                    print(f"   6. Raw LE: {value_raw_le:.4f} V", end="")
                    if 0.0 <= value_raw_le <= 500.0:
                        print(" ✅ PLAUSIBILE")
                    else:
                        print()
                    
                    # Determina quale è plausibile
                    plausible = []
                    if 0.0 <= value_be <= 500.0:
                        plausible.append(("BE standard", value_be))
                    if 0.0 <= value_le <= 500.0:
                        plausible.append(("LE registri", value_le))
                    if 0.0 <= value_sw <= 500.0:
                        plausible.append(("BE byte-swapped", value_sw))
                    if 0.0 <= value_le_full <= 500.0:
                        plausible.append(("LE completo", value_le_full))
                    if 0.0 <= value_raw_be <= 500.0:
                        plausible.append(("Raw BE", value_raw_be))
                    if 0.0 <= value_raw_le <= 500.0:
                        plausible.append(("Raw LE", value_raw_le))
                    
                    print()
                    if plausible:
                        print("   ✅ VALORI PLAUSIBILI TROVATI:")
                        for name, val in plausible:
                            print(f"      {name}: {val:.2f} V")
                    else:
                        print("   ⚠️  Nessun valore plausibile trovato")
                        print("   (Potrebbe essere un altro tipo di dato)")
        
        print()
        
        # Chiudi porta
        ser.close()
        print("✅ Porta seriale chiusa")
        
        return True
        
    except serial.SerialException as e:
        print(f"❌ ERRORE SERIALE: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        test_raw_serial()
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
