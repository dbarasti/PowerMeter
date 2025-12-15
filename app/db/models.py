"""
Modelli SQLAlchemy per il database.
Definisce le entità: User, TestSession, Measurement.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SessionStatus(str, Enum):
    """Stati possibili di una sessione di test."""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DeviceType(str, Enum):
    """Tipi di dispositivi misurati."""
    HEATER = "heater"  # Stufa
    FAN = "fan"        # Ventilatore


class User(Base):
    """
    Utente per autenticazione.
    Sistema semplice: un solo utente admin (estendibile in futuro).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User(username='{self.username}')>"


class TestSession(Base):
    """
    Sessione di test termico.
    Ogni prova è una TestSession con metadata e parametri.
    """
    __tablename__ = "test_sessions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metadata
    truck_plate = Column(String(20), nullable=False, index=True)  # Targa camion
    internal_surface_m2 = Column(Float, nullable=True)  # Superficie interna in m²
    external_surface_m2 = Column(Float, nullable=True)  # Superficie esterna in m²
    notes = Column(Text)  # Note libere
    
    # Parametri test
    duration_minutes = Column(Integer, nullable=True)  # Durata prevista in minuti (None = durata illimitata)
    sample_rate_seconds = Column(Integer, nullable=False, default=5)  # Frequenza campionamento
    
    # Stato e timestamp
    status = Column(String(20), nullable=False, default=SessionStatus.IDLE.value, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Timestamp creazione/modifica
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relazioni
    measurements = relationship("Measurement", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TestSession(id={self.id}, truck='{self.truck_plate}', status='{self.status}')>"


class Measurement(Base):
    """
    Misurazione di potenza ed energia da un SDM120.
    Ogni misura è associata a una TestSession e a un device (heater/fan).
    """
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False, index=True)
    
    # Device
    device_type = Column(String(20), nullable=False, index=True)  # "heater" o "fan"
    
    # Misure SDM120
    power_w = Column(Float, nullable=False)  # Potenza istantanea in Watt
    energy_kwh = Column(Float, nullable=False)  # Energia accumulata in kWh
    voltage_v = Column(Float, nullable=True)  # Tensione in Volt
    frequency_hz = Column(Float, nullable=True)  # Frequenza in Hz
    
    # Timestamp misura
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relazioni
    session = relationship("TestSession", back_populates="measurements")
    
    def __repr__(self):
        return f"<Measurement(id={self.id}, device='{self.device_type}', power={self.power_w}W)>"


class KCoefficient(Base):
    """
    Coefficiente di dispersione termica (trasmittanza globale U).
    Calcolato usando superficie equivalente, energia totale e temperature.
    """
    __tablename__ = "k_coefficients"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False, unique=True, index=True)
    
    # Input utente
    temp_internal_avg = Column(Float, nullable=False)  # Temperatura media interna (°C)
    temp_external_avg = Column(Float, nullable=False)  # Temperatura media esterna (°C)
    
    # Valori calcolati
    equivalent_surface_m2 = Column(Float, nullable=True)  # A_eq = sqrt(A_int * A_ext)
    avg_power_w = Column(Float, nullable=True)  # P_media = E_tot / durata (in W)
    delta_t = Column(Float, nullable=True)  # ΔT = T_int - T_ext (°C)
    u_value = Column(Float, nullable=True)  # U = P_media / (A_eq * ΔT) in W/m²K
    
    # Metadata calcolo
    calculated_at = Column(DateTime, default=datetime.utcnow)
    calculation_method = Column(String(50), default="geometric_mean")  # Metodo usato
    
    # Relazioni
    session = relationship("TestSession", uselist=False)
    
    def __repr__(self):
        return f"<KCoefficient(session_id={self.session_id}, u_value={self.u_value} W/m²K)>"

