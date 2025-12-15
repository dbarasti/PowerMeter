"""
Script per generare dati di esempio nel database.
Crea una sessione di test con misurazioni simulate per stufa e ventilatore.
"""
import sys
from datetime import datetime, timedelta
import random

# Aggiungi il path del progetto
sys.path.insert(0, '.')

from app.db.database import SessionLocal, init_db
from app.db.models import TestSession, Measurement, SessionStatus, DeviceType
from app.services.sessions import SessionService

def generate_sample_data():
    """Genera dati di esempio per una sessione di test."""
    db = SessionLocal()
    
    try:
        # Crea una sessione di test
        session_service = SessionService(db)
        session = session_service.create_session(
            truck_plate="ABC123XY",
            duration_minutes=60,
            sample_rate_seconds=5,
            cell_dimensions="3x2x2 m",
            notes="Sessione di test con dati simulati"
        )
        
        print(f"✓ Sessione creata: ID={session.id}, Targa={session.truck_plate}")
        
        # Imposta la sessione come completata
        session.status = SessionStatus.COMPLETED.value
        session.started_at = datetime.utcnow() - timedelta(hours=1)
        session.completed_at = datetime.utcnow()
        db.commit()
        
        # Genera misurazioni simulate
        # Simula 1 ora di acquisizione con campionamento ogni 5 secondi
        # = 720 misurazioni (3600 secondi / 5 secondi)
        num_measurements = 720
        
        # Timestamp iniziale (1 ora fa)
        start_time = datetime.utcnow() - timedelta(hours=1)
        
        # Parametri simulazione
        # Stufa: potenza variabile tra 2000-3000W, energia crescente
        heater_base_power = 2500
        heater_power_variation = 500
        
        # Ventilatore: potenza variabile tra 500-800W, energia crescente
        fan_base_power = 650
        fan_power_variation = 150
        
        heater_energy = 0.0
        fan_energy = 0.0
        
        print(f"✓ Generazione {num_measurements} misurazioni...")
        
        for i in range(num_measurements):
            # Calcola timestamp
            timestamp = start_time + timedelta(seconds=i * 5)
            
            # Simula potenza stufa (con variazione casuale e trend)
            heater_power = heater_base_power + random.uniform(-heater_power_variation, heater_power_variation)
            # Aggiungi un leggero trend (aumenta leggermente nel tempo)
            heater_power += (i / num_measurements) * 100
            
            # Calcola energia accumulata (Wh -> kWh)
            # Energia = potenza * tempo (in ore)
            # Ogni misurazione è a 5 secondi di distanza = 5/3600 ore
            time_hours = 5 / 3600.0
            heater_energy += (heater_power * time_hours) / 1000.0  # Converti Wh in kWh
            
            # Simula potenza ventilatore
            fan_power = fan_base_power + random.uniform(-fan_power_variation, fan_power_variation)
            fan_power += (i / num_measurements) * 50  # Leggero trend
            
            # Calcola energia ventilatore
            fan_energy += (fan_power * time_hours) / 1000.0
            
            # Crea misurazione stufa
            heater_measurement = Measurement(
                session_id=session.id,
                device_type=DeviceType.HEATER.value,
                power_w=round(heater_power, 2),
                energy_kwh=round(heater_energy, 3),
                timestamp=timestamp
            )
            db.add(heater_measurement)
            
            # Crea misurazione ventilatore
            fan_measurement = Measurement(
                session_id=session.id,
                device_type=DeviceType.FAN.value,
                power_w=round(fan_power, 2),
                energy_kwh=round(fan_energy, 3),
                timestamp=timestamp
            )
            db.add(fan_measurement)
            
            # Commit ogni 100 misurazioni per performance
            if (i + 1) % 100 == 0:
                db.commit()
                print(f"  Generati {i + 1}/{num_measurements} misurazioni...")
        
        # Commit finale
        db.commit()
        
        print(f"✓ Dati generati con successo!")
        print(f"  - Sessione ID: {session.id}")
        print(f"  - Misurazioni stufa: {num_measurements}")
        print(f"  - Misurazioni ventilatore: {num_measurements}")
        print(f"  - Energia totale stufa: {heater_energy:.3f} kWh")
        print(f"  - Energia totale ventilatore: {fan_energy:.3f} kWh")
        print(f"\nPuoi visualizzare i dati su: http://localhost:5173/session/{session.id}")
        
    except Exception as e:
        print(f"✗ Errore: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Generazione Dati di Esempio ===")
    print()
    
    # Inizializza database se necessario
    init_db()
    
    generate_sample_data()

