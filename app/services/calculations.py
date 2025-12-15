"""
Servizio per calcoli statistici e analisi dati.
Calcola medie, totali, e prepara dati per grafici.
Placeholder per coefficiente K.
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.db.models import Measurement, DeviceType

logger = logging.getLogger(__name__)


class CalculationService:
    """Servizio per calcoli su misurazioni."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_session_statistics(self, session_id: int) -> Dict:
        """
        Calcola statistiche per una sessione di test.
        
        Returns:
            Dict con statistiche per heater e fan:
            {
                "heater": {
                    "avg_power_w": float,
                    "max_power_w": float,
                    "min_power_w": float,
                    "total_energy_kwh": float,
                    "measurement_count": int
                },
                "fan": { ... }
            }
        """
        stats = {}
        
        for device_type in [DeviceType.HEATER.value, DeviceType.FAN.value]:
            measurements = self.db.query(Measurement).filter(
                Measurement.session_id == session_id,
                Measurement.device_type == device_type
            ).all()
            
            if not measurements:
                stats[device_type] = {
                    "avg_power_w": 0.0,
                    "max_power_w": 0.0,
                    "min_power_w": 0.0,
                    "total_energy_kwh": 0.0,
                    "measurement_count": 0
                }
                continue
            
            powers = [m.power_w for m in measurements]
            energies = [m.energy_kwh for m in measurements]
            
            # Energia totale = ultima energia - prima energia
            total_energy = energies[-1] - energies[0] if len(energies) > 1 else 0.0
            
            stats[device_type] = {
                "avg_power_w": sum(powers) / len(powers),
                "max_power_w": max(powers),
                "min_power_w": min(powers),
                "total_energy_kwh": total_energy,
                "measurement_count": len(measurements)
            }
        
        return stats
    
    def get_session_data_for_chart(
        self,
        session_id: int,
        device_type: str,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Recupera dati per grafico (timestamp, power, energy).
        
        Args:
            session_id: ID sessione
            device_type: "heater" o "fan"
            limit: Numero massimo di punti (per performance)
            
        Returns:
            Lista di dict con keys: timestamp, power_w, energy_kwh
        """
        measurements = self.db.query(Measurement).filter(
            Measurement.session_id == session_id,
            Measurement.device_type == device_type
        ).order_by(Measurement.timestamp).limit(limit).all()
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "power_w": m.power_w,
                "energy_kwh": m.energy_kwh
            }
            for m in measurements
        ]
    
    def calculate_k_coefficient(self, session_id: int) -> Optional[float]:
        """
        Placeholder per calcolo coefficiente K.
        Per ora restituisce None.
        
        Args:
            session_id: ID sessione
            
        Returns:
            Valore K calcolato (None se non implementato)
        """
        # TODO: Implementare calcolo coefficiente K
        # Il coefficiente K è un parametro termico che dipende da:
        # - Potenza stufa
        # - Potenza ventilatore
        # - Temperatura ambiente
        # - Dimensioni cella
        # - Altri parametri fisici
        
        logger.info(f"Calcolo K per sessione {session_id} - PLACEHOLDER (non implementato)")
        return None

