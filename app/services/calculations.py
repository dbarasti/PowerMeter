"""
Servizio per calcoli statistici e analisi dati.
Calcola medie, totali, e prepara dati per grafici.
Calcolo coefficiente di dispersione termica (trasmittanza globale U).
"""
import logging
import math
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import Measurement, DeviceType, TestSession, KCoefficient

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
                    "avg_voltage_v": float,
                    "avg_frequency_hz": float,
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
                    "avg_voltage_v": 0.0,
                    "avg_frequency_hz": 0.0,
                    "measurement_count": 0
                }
                continue
            
            powers = [m.power_w for m in measurements]
            voltages = [m.voltage_v for m in measurements if m.voltage_v is not None]
            frequencies = [m.frequency_hz for m in measurements if m.frequency_hz is not None]
            
            # Calcola energia cumulata dalla potenza (energia della sessione)
            calculated_energies = self.calculate_energy_from_power(measurements)
            # Energia totale = ultima energia calcolata (energia totale della sessione)
            total_energy = calculated_energies[-1] if calculated_energies else 0.0
            
            stats[device_type] = {
                "avg_power_w": sum(powers) / len(powers),
                "max_power_w": max(powers),
                "min_power_w": min(powers),
                "total_energy_kwh": total_energy,
                "avg_voltage_v": sum(voltages) / len(voltages) if voltages else None,
                "avg_frequency_hz": sum(frequencies) / len(frequencies) if frequencies else None,
                "measurement_count": len(measurements)
            }
        
        return stats
    
    def calculate_energy_from_power(
        self,
        measurements: List[Measurement]
    ) -> List[float]:
        """
        Calcola energia cumulata (kWh) integrando la potenza nel tempo.
        
        Usa il metodo del trapezio per integrare la potenza tra i campioni.
        Energia = integrale(P(t) dt) in kWh
        
        Args:
            measurements: Lista di misurazioni ordinate per timestamp
            
        Returns:
            Lista di energia cumulata in kWh per ogni misurazione
        """
        if len(measurements) < 2:
            return [0.0] * len(measurements)
        
        energies = [0.0]  # Prima misurazione: energia = 0
        
        # Calcola energia per ogni intervallo usando metodo del trapezio
        for i in range(1, len(measurements)):
            prev_measurement = measurements[i-1]
            curr_measurement = measurements[i]
            
            # Calcola delta tempo in ore
            delta_time = (
                curr_measurement.timestamp - prev_measurement.timestamp
            ).total_seconds() / 3600.0
            
            # Potenza media nell'intervallo (metodo del trapezio)
            avg_power = (
                prev_measurement.power_w + curr_measurement.power_w
            ) / 2.0
            
            # Energia nell'intervallo = potenza media * tempo (in ore)
            # Risultato già in kWh (W * h / 1000 = kWh)
            energy_increment = (avg_power * delta_time) / 1000.0
            
            # Aggiungi all'energia cumulata
            cumulative_energy = energies[-1] + energy_increment
            energies.append(cumulative_energy)
        
        return energies
    
    def get_session_data_for_chart(
        self,
        session_id: int,
        device_type: str,
        max_points: Optional[int] = None
    ) -> List[Dict]:
        """
        Recupera dati per grafico (timestamp, power, energy, voltage, frequency).
        
        L'energia mostrata è calcolata integrando la potenza nel tempo (energia della sessione),
        non l'energia totale accumulata del dispositivo.
        
        Se ci sono più di max_points (default: nessun limite), applica downsampling intelligente
        che mantiene i punti critici (min, max, inizio, fine) e campiona uniformemente il resto.
        
        Args:
            session_id: ID sessione
            device_type: "heater" o "fan"
            max_points: Numero massimo di punti (None = nessun limite, tutti i dati)
            
        Returns:
            Lista di dict con keys: timestamp, power_w, energy_kwh, voltage_v, frequency_hz
            energy_kwh è l'energia cumulata calcolata dalla potenza campionata
        """
        # Recupera tutte le misurazioni (senza limite)
        measurements = self.db.query(Measurement).filter(
            Measurement.session_id == session_id,
            Measurement.device_type == device_type
        ).order_by(Measurement.timestamp).all()
        
        if not measurements:
            return []
        
        # Se max_points è specificato e ci sono più punti, applica downsampling intelligente
        if max_points and len(measurements) > max_points:
            measurements = self._downsample_measurements(measurements, max_points)
        
        # Calcola energia cumulata dalla potenza
        calculated_energies = self.calculate_energy_from_power(measurements)
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "power_w": m.power_w,
                "energy_kwh": calculated_energies[i],  # Usa energia calcolata
                "voltage_v": m.voltage_v,
                "frequency_hz": m.frequency_hz
            }
            for i, m in enumerate(measurements)
        ]
    
    def _downsample_measurements(
        self,
        measurements: List[Measurement],
        target_count: int
    ) -> List[Measurement]:
        """
        Downsampling intelligente che mantiene punti critici e campiona uniformemente.
        
        Mantiene sempre:
        - Primo punto (inizio)
        - Ultimo punto (fine)
        - Punti con valore min/max di potenza
        
        Poi campiona uniformemente il resto per raggiungere target_count.
        
        Args:
            measurements: Lista completa di misurazioni
            target_count: Numero target di punti dopo downsampling
            
        Returns:
            Lista di misurazioni downsampled
        """
        if len(measurements) <= target_count:
            return measurements
        
        # Trova min e max di potenza
        min_power_idx = min(range(len(measurements)), key=lambda i: measurements[i].power_w)
        max_power_idx = max(range(len(measurements)), key=lambda i: measurements[i].power_w)
        
        # Indici critici da mantenere sempre
        critical_indices = {0, len(measurements) - 1, min_power_idx, max_power_idx}
        
        # Calcola step per campionamento uniforme
        # Sottraiamo i punti critici dal target
        remaining_slots = target_count - len(critical_indices)
        if remaining_slots <= 0:
            # Se target_count è troppo piccolo, restituisci solo i punti critici
            return [measurements[i] for i in sorted(critical_indices)]
        
        # Campiona uniformemente il resto
        step = len(measurements) / remaining_slots
        sampled_indices = set()
        
        for i in range(remaining_slots):
            idx = int(i * step)
            if idx < len(measurements):
                sampled_indices.add(idx)
        
        # Combina indici critici e campionati
        all_indices = sorted(critical_indices | sampled_indices)
        
        # Se abbiamo ancora troppi punti, prendi uniformemente
        if len(all_indices) > target_count:
            step = len(all_indices) / target_count
            final_indices = [
                all_indices[int(i * step)]
                for i in range(target_count)
            ]
            all_indices = sorted(set(final_indices))
        
        return [measurements[i] for i in all_indices]
    
    def calculate_u_coefficient(
        self,
        session_id: int,
        temp_internal_avg: float,
        temp_external_avg: float
    ) -> Dict:
        """
        Calcola il coefficiente di dispersione termica (trasmittanza globale U).
        
        Formula:
        - A_eq = sqrt(A_int * A_ext)  [superficie equivalente]
        - P_media = E_tot / durata_prova  [potenza media in W]
        - ΔT = T_int_media - T_ext_media  [differenza temperatura in °C]
        - U = P_media / (A_eq * ΔT)  [coefficiente U in W/m²K]
        
        Args:
            session_id: ID sessione
            temp_internal_avg: Temperatura media interna (°C)
            temp_external_avg: Temperatura media esterna (°C)
            
        Returns:
            Dict con tutti i valori calcolati:
            {
                "equivalent_surface_m2": float,
                "avg_power_w": float,
                "delta_t": float,
                "u_value": float,
                "total_energy_kwh": float,
                "duration_seconds": float
            }
            
        Raises:
            ValueError: Se mancano dati necessari per il calcolo
        """
        # Recupera sessione
        session = self.db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()
        
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        # Verifica che le superfici siano disponibili
        if not session.internal_surface_m2 or not session.external_surface_m2:
            raise ValueError(
                "Superfici interna ed esterna devono essere specificate "
                "per calcolare il coefficiente U"
            )
        
        # Calcola durata della prova in secondi
        if not session.started_at or not session.completed_at:
            raise ValueError(
                "La sessione deve essere completata (con started_at e completed_at) "
                "per calcolare il coefficiente U"
            )
        
        duration_timedelta = session.completed_at - session.started_at
        duration_seconds = duration_timedelta.total_seconds()
        
        if duration_seconds <= 0:
            raise ValueError("Durata della prova deve essere maggiore di zero")
        
        # Calcola energia totale (somma heater + fan)
        stats = self.get_session_statistics(session_id)
        total_energy_kwh = (
            stats.get("heater", {}).get("total_energy_kwh", 0.0) +
            stats.get("fan", {}).get("total_energy_kwh", 0.0)
        )
        
        if total_energy_kwh <= 0:
            raise ValueError("Energia totale deve essere maggiore di zero")
        
        # Converti energia da kWh a Wh
        total_energy_wh = total_energy_kwh * 1000.0
        
        # Calcoli secondo la formula:
        # U = P_media / (A_eq * ΔT)
        # dove:
        # - A_eq = sqrt(A_int * A_ext) [superficie equivalente, media geometrica]
        # - P_media = E_tot / durata [potenza media in W]
        # - ΔT = T_int - T_ext [differenza temperatura in °C]
        # - U [coefficiente di trasmittanza globale in W/m²K]
        
        # 1. Superficie equivalente (media geometrica)
        # A_eq = sqrt(A_int * A_ext)
        equivalent_surface_m2 = math.sqrt(
            session.internal_surface_m2 * session.external_surface_m2
        )
        
        # 2. Potenza media (in W)
        # P_media = E_tot (Wh) / durata (h) = E_tot (Wh) / (durata (s) / 3600)
        # P_media = E_tot (Wh) * 3600 / durata (s) = E_tot (Wh) / durata (s) * 3600
        avg_power_w = total_energy_wh / duration_seconds * 3600.0  # Wh -> W
        
        # 3. Differenza temperatura
        # ΔT = T_int - T_ext
        delta_t = temp_internal_avg - temp_external_avg
        
        if delta_t <= 0:
            raise ValueError(
                "La temperatura interna deve essere maggiore della temperatura esterna"
            )
        
        # 4. Coefficiente U (trasmittanza globale)
        # U = P_media / (A_eq * ΔT)
        # Unità: W / (m² * K) = W/m²K
        if equivalent_surface_m2 <= 0:
            raise ValueError("Superficie equivalente deve essere maggiore di zero")
        
        u_value = avg_power_w / (equivalent_surface_m2 * delta_t)
        
        result = {
            "equivalent_surface_m2": equivalent_surface_m2,
            "avg_power_w": avg_power_w,
            "delta_t": delta_t,
            "u_value": u_value,
            "total_energy_kwh": total_energy_kwh,
            "duration_seconds": duration_seconds
        }
        
        logger.info(
            f"Coefficiente U calcolato per sessione {session_id}: "
            f"U = {u_value:.4f} W/m²K"
        )
        
        return result
    
    def save_u_coefficient(
        self,
        session_id: int,
        temp_internal_avg: float,
        temp_external_avg: float
    ) -> KCoefficient:
        """
        Calcola e salva il coefficiente U nel database.
        
        Args:
            session_id: ID sessione
            temp_internal_avg: Temperatura media interna (°C)
            temp_external_avg: Temperatura media esterna (°C)
            
        Returns:
            KCoefficient salvato
        """
        # Calcola coefficiente U
        calc_result = self.calculate_u_coefficient(
            session_id, temp_internal_avg, temp_external_avg
        )
        
        # Cerca coefficiente esistente o crea nuovo
        k_coeff = self.db.query(KCoefficient).filter(
            KCoefficient.session_id == session_id
        ).first()
        
        if k_coeff:
            # Aggiorna esistente
            k_coeff.temp_internal_avg = temp_internal_avg
            k_coeff.temp_external_avg = temp_external_avg
            k_coeff.equivalent_surface_m2 = calc_result["equivalent_surface_m2"]
            k_coeff.avg_power_w = calc_result["avg_power_w"]
            k_coeff.delta_t = calc_result["delta_t"]
            k_coeff.u_value = calc_result["u_value"]
            k_coeff.calculated_at = datetime.utcnow()
        else:
            # Crea nuovo
            k_coeff = KCoefficient(
                session_id=session_id,
                temp_internal_avg=temp_internal_avg,
                temp_external_avg=temp_external_avg,
                equivalent_surface_m2=calc_result["equivalent_surface_m2"],
                avg_power_w=calc_result["avg_power_w"],
                delta_t=calc_result["delta_t"],
                u_value=calc_result["u_value"],
                calculated_at=datetime.utcnow()
            )
            self.db.add(k_coeff)
        
        self.db.commit()
        self.db.refresh(k_coeff)
        
        logger.info(
            f"Coefficiente U salvato per sessione {session_id}: "
            f"U = {k_coeff.u_value:.4f} W/m²K"
        )
        
        return k_coeff
    
    def get_u_coefficient(self, session_id: int) -> Optional[KCoefficient]:
        """
        Recupera il coefficiente U calcolato per una sessione.
        
        Args:
            session_id: ID sessione
            
        Returns:
            KCoefficient se esiste, None altrimenti
        """
        return self.db.query(KCoefficient).filter(
            KCoefficient.session_id == session_id
        ).first()

