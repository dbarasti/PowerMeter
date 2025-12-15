"""
API endpoints per dati e statistiche.
Recupero misurazioni, statistiche, export CSV.
Calcolo coefficiente di dispersione termica.
"""
import logging
import csv
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Measurement
from app.api.auth import get_current_user, User
from app.services.calculations import CalculationService
from app.services.sessions import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])


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
    """Esporta dati di una sessione in formato CSV."""
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
    
    # Genera CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["timestamp", "device", "power_w", "energy_kwh", "voltage_v", "frequency_hz"])
    
    # Dati
    for m in measurements:
        writer.writerow([
            m.timestamp.isoformat(),
            m.device_type,
            m.power_w,
            m.energy_kwh,
            m.voltage_v if m.voltage_v is not None else "",
            m.frequency_hz if m.frequency_hz is not None else ""
        ])
    
    output.seek(0)
    
    # Response con filename
    filename = f"session_{session_id}_{session.truck_plate}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
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

