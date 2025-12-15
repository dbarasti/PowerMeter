"""
API endpoints per gestione sessioni di test.
CRUD operations, avvio/stop acquisizione.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import TestSession
from app.api.auth import get_current_user, User
from app.services.sessions import SessionService
from app.services.acquisition import AcquisitionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Global acquisition service instance (gestita dal main)
_acquisition_service: Optional[AcquisitionService] = None


def set_acquisition_service(service: AcquisitionService):
    """Imposta il servizio di acquisizione globale."""
    global _acquisition_service
    _acquisition_service = service


# Pydantic models
class TestSessionCreate(BaseModel):
    truck_plate: str
    duration_minutes: Optional[int] = None  # None = durata illimitata
    sample_rate_seconds: int = 5
    internal_surface_m2: Optional[float] = None
    external_surface_m2: Optional[float] = None
    notes: Optional[str] = None


class TestSessionUpdate(BaseModel):
    truck_plate: Optional[str] = None
    internal_surface_m2: Optional[float] = None
    external_surface_m2: Optional[float] = None
    notes: Optional[str] = None


class TestSessionResponse(BaseModel):
    id: int
    truck_plate: str
    internal_surface_m2: Optional[float]
    external_surface_m2: Optional[float]
    notes: Optional[str]
    duration_minutes: Optional[int]  # None = durata illimitata
    sample_rate_seconds: int
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def session_to_dict(session: TestSession) -> dict:
    """Converte una TestSession SQLAlchemy in dict per Pydantic."""
    return {
        "id": session.id,
        "truck_plate": session.truck_plate,
        "internal_surface_m2": session.internal_surface_m2,
        "external_surface_m2": session.external_surface_m2,
        "notes": session.notes,
        "duration_minutes": session.duration_minutes,
        "sample_rate_seconds": session.sample_rate_seconds,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "updated_at": session.updated_at.isoformat() if session.updated_at else "",
    }


@router.post("", response_model=TestSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: TestSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crea una nuova sessione di test."""
    service = SessionService(db)
    session = service.create_session(
        truck_plate=session_data.truck_plate,
        duration_minutes=session_data.duration_minutes,
        sample_rate_seconds=session_data.sample_rate_seconds,
        internal_surface_m2=session_data.internal_surface_m2,
        external_surface_m2=session_data.external_surface_m2,
        notes=session_data.notes
    )
    return TestSessionResponse(**session_to_dict(session))


@router.get("", response_model=List[TestSessionResponse])
async def list_sessions(
    status_filter: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista tutte le sessioni di test."""
    service = SessionService(db)
    sessions = service.get_all_sessions(limit=limit, status=status_filter)
    return [TestSessionResponse(**session_to_dict(s)) for s in sessions]


@router.get("/{session_id}", response_model=TestSessionResponse)
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recupera una sessione per ID."""
    service = SessionService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return TestSessionResponse(**session_to_dict(session))


@router.put("/{session_id}", response_model=TestSessionResponse)
async def update_session(
    session_id: int,
    session_data: TestSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aggiorna metadata di una sessione."""
    service = SessionService(db)
    session = service.update_session(
        session_id=session_id,
        truck_plate=session_data.truck_plate,
        internal_surface_m2=session_data.internal_surface_m2,
        external_surface_m2=session_data.external_surface_m2,
        notes=session_data.notes
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or cannot be modified")
    return TestSessionResponse(**session_to_dict(session))


@router.post("/{session_id}/start", status_code=status.HTTP_200_OK)
async def start_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Avvia acquisizione dati per una sessione."""
    if not _acquisition_service:
        raise HTTPException(
            status_code=500,
            detail="Servizio di acquisizione non disponibile. Riavvia l'applicazione."
        )
    
    # Verifica che la sessione esista
    service = SessionService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessione non trovata")
    
    # Avvia acquisizione
    success, error_message = _acquisition_service.start(session_id, session.sample_rate_seconds)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=error_message or "Impossibile avviare l'acquisizione"
        )
    
    return {"message": "Acquisizione avviata con successo", "session_id": session_id}


@router.post("/{session_id}/stop", status_code=status.HTTP_200_OK)
async def stop_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ferma acquisizione dati per una sessione."""
    if not _acquisition_service:
        raise HTTPException(status_code=500, detail="Acquisition service not available")
    
    # Verifica che la sessione corrente corrisponda
    current_session_id = _acquisition_service.get_current_session_id()
    if current_session_id != session_id:
        raise HTTPException(status_code=400, detail="Session is not currently running")
    
    _acquisition_service.stop()
    return {"message": "Acquisition stopped", "session_id": session_id}


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def cancel_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancella una sessione."""
    service = SessionService(db)
    success = service.cancel_session(session_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel session")
    return {"message": "Session cancelled", "session_id": session_id}

