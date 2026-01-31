"""
API endpoints per dati e statistiche.
Recupero misurazioni, statistiche, export CSV.
Calcolo coefficiente di dispersione termica.
"""
import logging
import csv
import zipfile
from io import StringIO, BytesIO
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Measurement
from app.api.auth import get_current_user, User
from app.services.calculations import CalculationService
from app.services.sessions import SessionService
from app.config import TIMEZONE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])


def utc_to_local(utc_dt: datetime, local_tz: ZoneInfo) -> datetime:
    """
    Converte un datetime UTC (naive o aware) in fuso orario locale.
    
    Args:
        utc_dt: Datetime UTC (può essere naive o timezone-aware)
        local_tz: Fuso orario di destinazione
        
    Returns:
        Datetime nel fuso orario locale (timezone-aware)
    """
    # Se il datetime è naive, assumiamo che sia UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo('UTC'))
    
    # Converti in fuso orario locale
    return utc_dt.astimezone(local_tz)


class UCoefficientRequest(BaseModel):
    """Request per calcolo coefficiente U."""
    temp_internal_avg: float  # Temperatura media interna (°C)
    temp_external_avg: float  # Temperatura media esterna (°C)


@router.get("/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recupera statistiche per una sessione."""
    # Verifica che la sessione esista
    session_service = SessionService(db)
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calcola statistiche
    calc_service = CalculationService(db)
    stats = calc_service.get_session_statistics(session_id)
    
    return stats


@router.get("/sessions/{session_id}/chart/{device_type}")
async def get_chart_data(
    session_id: int,
    device_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recupera dati per grafico (timestamp, power, energy)."""
    if device_type not in ["heater", "fan"]:
        raise HTTPException(status_code=400, detail="Invalid device_type (must be 'heater' or 'fan')")
    
    # Verifica che la sessione esista
    session_service = SessionService(db)
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Recupera dati
    calc_service = CalculationService(db)
    data = calc_service.get_session_data_for_chart(session_id, device_type)
    
    return {"data": data}


@router.get("/sessions/{session_id}/export")
async def export_session_csv(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Esporta dati di una sessione in formato CSV.
    Crea un file CSV per ogni ora dell'orologio e li comprime in un archivio ZIP.
    """
    # Verifica che la sessione esista
    session_service = SessionService(db)
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Recupera tutte le misurazioni
    measurements = db.query(Measurement).filter(
        Measurement.session_id == session_id
    ).order_by(Measurement.timestamp).all()
    
    if not measurements:
        raise HTTPException(status_code=404, detail="No measurements found for this session")
    
    # Trova il timestamp della prima misurazione (inizio prova) in UTC
    start_time_utc = measurements[0].timestamp
    
    # Converti in fuso orario locale per il raggruppamento
    local_tz = ZoneInfo(TIMEZONE)
    
    # Raggruppa le misurazioni per ora dell'orologio locale
    # Usa l'ora arrotondata (es: 14:25 -> 14:00, 15:10 -> 15:00)
    measurements_by_hour = defaultdict(list)  # {hour_key: [measurements]}
    
    for m in measurements:
        # Converti timestamp UTC in fuso orario locale
        local_time = utc_to_local(m.timestamp, local_tz)
        # Arrotonda il timestamp all'ora locale (minuti, secondi, microsecondi a zero)
        hour_key = local_time.replace(minute=0, second=0, microsecond=0)
        measurements_by_hour[hour_key].append(m)
    
    # Calcola medie orarie per ogni ora (per le colonne aggiuntive)
    # Raggruppa per "ora relativa" dall'inizio della prova (usa UTC per calcoli interni)
    hourly_heater_power = defaultdict(list)  # {hour_index: [power_values]}
    hourly_fan_power = defaultdict(list)
    
    for m in measurements:
        elapsed_seconds = (m.timestamp - start_time_utc).total_seconds()
        hour_index = int(elapsed_seconds // 3600)
        
        if m.device_type == "heater":
            hourly_heater_power[hour_index].append(m.power_w)
        elif m.device_type == "fan":
            hourly_fan_power[hour_index].append(m.power_w)
    
    # Calcola le medie per ogni ora relativa
    hourly_heater_avg = {}
    hourly_fan_avg = {}
    
    for hour_index, powers in hourly_heater_power.items():
        hourly_heater_avg[hour_index] = sum(powers) / len(powers) if powers else 0.0
    
    for hour_index, powers in hourly_fan_power.items():
        hourly_fan_avg[hour_index] = sum(powers) / len(powers) if powers else 0.0
    
    # Crea un archivio ZIP in memoria
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Genera un file CSV per ogni ora
        for hour_key, hour_measurements in sorted(measurements_by_hour.items()):
            # Formatta il nome del file con ora locale: session_1_ABC123_2024-01-15_14-00.csv
            hour_str = hour_key.strftime("%Y-%m-%d_%H-%M")
            csv_filename = f"session_{session_id}_{session.truck_plate}_{hour_str}.csv"
            
            # Crea il contenuto CSV per questa ora
            csv_output = StringIO()
            writer = csv.writer(csv_output)
            
            # Header
            writer.writerow([
                "timestamp", 
                "device", 
                "power_w", 
                "energy_kwh", 
                "voltage_v", 
                "frequency_hz",
                "avg_power_w_heater_hourly",
                "avg_power_w_fan_hourly"
            ])
            
            # Dati per questa ora
            for m in hour_measurements:
                # Calcola l'indice dell'ora relativa per questa misurazione (usa UTC)
                elapsed_seconds = (m.timestamp - start_time_utc).total_seconds()
                hour_index = int(elapsed_seconds // 3600)
                
                # Recupera le medie orarie
                heater_avg = hourly_heater_avg.get(hour_index, 0.0)
                fan_avg = hourly_fan_avg.get(hour_index, 0.0)
                
                # Converti timestamp UTC in fuso orario locale per il CSV
                local_timestamp = utc_to_local(m.timestamp, local_tz)
                
                writer.writerow([
                    local_timestamp.isoformat(),  # Timestamp in fuso orario locale
                    m.device_type,
                    m.power_w,
                    m.energy_kwh,
                    m.voltage_v if m.voltage_v is not None else "",
                    m.frequency_hz if m.frequency_hz is not None else "",
                    f"{heater_avg:.2f}" if heater_avg > 0 else "",
                    f"{fan_avg:.2f}" if fan_avg > 0 else ""
                ])
            
            # Aggiungi il file CSV all'archivio ZIP
            csv_output.seek(0)
            zip_file.writestr(csv_filename, csv_output.getvalue())
    
    zip_buffer.seek(0)
    
    # Response con filename ZIP
    zip_filename = f"session_{session_id}_{session.truck_plate}.zip"
    
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )


@router.post("/sessions/{session_id}/u-coefficient")
async def calculate_u_coefficient(
    session_id: int,
    request: UCoefficientRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calcola e salva il coefficiente di dispersione termica (trasmittanza globale U).
    
    Richiede:
    - temp_internal_avg: Temperatura media interna (°C)
    - temp_external_avg: Temperatura media esterna (°C)
    
    Calcola:
    - Superficie equivalente: A_eq = sqrt(A_int * A_ext)
    - Potenza media: P_media = E_tot / durata (in W)
    - Delta T: ΔT = T_int - T_ext
    - Coefficiente U: U = P_media / (A_eq * ΔT) in W/m²K
    """
    # Verifica che la sessione esista
    session_service = SessionService(db)
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calcola e salva coefficiente U
    calc_service = CalculationService(db)
    try:
        k_coeff = calc_service.save_u_coefficient(
            session_id,
            request.temp_internal_avg,
            request.temp_external_avg
        )
        
        return {
            "session_id": k_coeff.session_id,
            "temp_internal_avg": k_coeff.temp_internal_avg,
            "temp_external_avg": k_coeff.temp_external_avg,
            "equivalent_surface_m2": k_coeff.equivalent_surface_m2,
            "avg_power_w": k_coeff.avg_power_w,
            "delta_t": k_coeff.delta_t,
            "u_value": k_coeff.u_value,
            "calculated_at": k_coeff.calculated_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Errore nel calcolo coefficiente U: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nel calcolo: {str(e)}")


@router.get("/sessions/{session_id}/u-coefficient")
async def get_u_coefficient(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recupera il coefficiente U calcolato per una sessione."""
    # Verifica che la sessione esista
    session_service = SessionService(db)
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Recupera coefficiente U
    calc_service = CalculationService(db)
    k_coeff = calc_service.get_u_coefficient(session_id)
    
    if not k_coeff:
        raise HTTPException(
            status_code=404,
            detail="Coefficiente U non ancora calcolato per questa sessione"
        )
    
    return {
        "session_id": k_coeff.session_id,
        "temp_internal_avg": k_coeff.temp_internal_avg,
        "temp_external_avg": k_coeff.temp_external_avg,
        "equivalent_surface_m2": k_coeff.equivalent_surface_m2,
        "avg_power_w": k_coeff.avg_power_w,
        "delta_t": k_coeff.delta_t,
        "u_value": k_coeff.u_value,
        "calculated_at": k_coeff.calculated_at.isoformat()
    }

