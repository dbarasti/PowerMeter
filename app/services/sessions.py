"""
Servizio per gestione sessioni di test.
CRUD operations, validazione, query.
"""
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.models import TestSession, SessionStatus

logger = logging.getLogger(__name__)


class SessionService:
    """Servizio per gestione TestSession."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(
        self,
        truck_plate: str,
        duration_minutes: Optional[int] = None,
        sample_rate_seconds: int = 5,
        internal_surface_m2: Optional[float] = None,
        external_surface_m2: Optional[float] = None,
        notes: Optional[str] = None
    ) -> TestSession:
        """
        Crea una nuova sessione di test.
        
        Args:
            truck_plate: Targa camion
            duration_minutes: Durata prevista in minuti (None = durata illimitata)
            sample_rate_seconds: Frequenza campionamento in secondi
            internal_surface_m2: Superficie interna in m² (opzionale)
            external_surface_m2: Superficie esterna in m² (opzionale)
            notes: Note libere (opzionale)
            
        Returns:
            TestSession creata
        """
        session = TestSession(
            truck_plate=truck_plate,
            duration_minutes=duration_minutes,
            sample_rate_seconds=sample_rate_seconds,
            internal_surface_m2=internal_surface_m2,
            external_surface_m2=external_surface_m2,
            notes=notes,
            status=SessionStatus.IDLE.value
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Sessione creata: ID={session.id}, truck={truck_plate}")
        return session
    
    def get_session(self, session_id: int) -> Optional[TestSession]:
        """Recupera una sessione per ID."""
        return self.db.query(TestSession).filter(TestSession.id == session_id).first()
    
    def get_all_sessions(
        self,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[TestSession]:
        """
        Recupera tutte le sessioni, ordinate per data creazione (più recenti prima).
        
        Args:
            limit: Numero massimo di risultati
            status: Filtra per status (opzionale)
        """
        query = self.db.query(TestSession)
        
        if status:
            query = query.filter(TestSession.status == status)
        
        return query.order_by(desc(TestSession.created_at)).limit(limit).all()
    
    def update_session(
        self,
        session_id: int,
        truck_plate: Optional[str] = None,
        internal_surface_m2: Optional[float] = None,
        external_surface_m2: Optional[float] = None,
        notes: Optional[str] = None
    ) -> Optional[TestSession]:
        """
        Aggiorna metadata di una sessione.
        
        Le superfici (internal_surface_m2, external_surface_m2) e le note possono
        essere modificate in qualsiasi stato (IDLE, RUNNING, COMPLETED).
        La targa può essere modificata solo se la sessione è in stato IDLE.
        
        Args:
            session_id: ID sessione
            truck_plate: Nuova targa (opzionale, solo se IDLE)
            internal_surface_m2: Nuova superficie interna in m² (opzionale, sempre modificabile)
            external_surface_m2: Nuova superficie esterna in m² (opzionale, sempre modificabile)
            notes: Nuove note (opzionale, sempre modificabile)
            
        Returns:
            TestSession aggiornata, None se non trovata o non modificabile
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Targa può essere modificata solo se IDLE
        if truck_plate is not None:
            if session.status != SessionStatus.IDLE.value:
                logger.warning(
                    f"Impossibile modificare targa per sessione {session_id}: "
                    f"stato={session.status} (solo IDLE consentito)"
                )
            else:
                session.truck_plate = truck_plate
        
        # Superfici e note possono essere sempre modificate
        if internal_surface_m2 is not None:
            session.internal_surface_m2 = internal_surface_m2
        if external_surface_m2 is not None:
            session.external_surface_m2 = external_surface_m2
        if notes is not None:
            session.notes = notes
        
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(
            f"Sessione {session_id} aggiornata (stato={session.status}, "
            f"superfici modificate: {internal_surface_m2 is not None or external_surface_m2 is not None})"
        )
        
        return session
    
    def cancel_session(self, session_id: int) -> bool:
        """
        Cancella una sessione (solo se in stato IDLE o RUNNING).
        
        Args:
            session_id: ID sessione
            
        Returns:
            True se cancellata, False altrimenti
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        if session.status == SessionStatus.COMPLETED.value:
            logger.warning(f"Impossibile cancellare sessione {session_id}: già completata")
            return False
        
        session.status = SessionStatus.CANCELLED.value
        session.completed_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Sessione {session_id} cancellata")
        return True

