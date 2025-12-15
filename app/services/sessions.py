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
        duration_minutes: int,
        sample_rate_seconds: int = 5,
        cell_dimensions: Optional[str] = None,
        notes: Optional[str] = None
    ) -> TestSession:
        """
        Crea una nuova sessione di test.
        
        Args:
            truck_plate: Targa camion
            duration_minutes: Durata prevista in minuti
            sample_rate_seconds: Frequenza campionamento in secondi
            cell_dimensions: Dimensioni cella frigo (opzionale)
            notes: Note libere (opzionale)
            
        Returns:
            TestSession creata
        """
        session = TestSession(
            truck_plate=truck_plate,
            duration_minutes=duration_minutes,
            sample_rate_seconds=sample_rate_seconds,
            cell_dimensions=cell_dimensions,
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
        cell_dimensions: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[TestSession]:
        """
        Aggiorna metadata di una sessione (solo se in stato IDLE).
        
        Args:
            session_id: ID sessione
            truck_plate: Nuova targa (opzionale)
            cell_dimensions: Nuove dimensioni (opzionale)
            notes: Nuove note (opzionale)
            
        Returns:
            TestSession aggiornata, None se non trovata o non modificabile
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        if session.status != SessionStatus.IDLE.value:
            logger.warning(f"Impossibile modificare sessione {session_id}: stato={session.status}")
            return None
        
        if truck_plate is not None:
            session.truck_plate = truck_plate
        if cell_dimensions is not None:
            session.cell_dimensions = cell_dimensions
        if notes is not None:
            session.notes = notes
        
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
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

