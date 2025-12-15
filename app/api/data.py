"""
API endpoints per dati e statistiche.
Recupero misurazioni, statistiche, export CSV.
"""
import logging
import csv
from io import StringIO
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Measurement
from app.api.auth import get_current_user, User
from app.services.calculations import CalculationService
from app.services.sessions import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])


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
    writer.writerow(["timestamp", "device", "power_w", "energy_kwh"])
    
    # Dati
    for m in measurements:
        writer.writerow([
            m.timestamp.isoformat(),
            m.device_type,
            m.power_w,
            m.energy_kwh
        ])
    
    output.seek(0)
    
    # Response con filename
    filename = f"session_{session_id}_{session.truck_plate}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

