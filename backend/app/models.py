"""SQLAlchemy ORM models for NightWatch.

All models include composite indexes on (patient_id, timestamp) for rapid query retrieval,
and idempotent unique constraints on sensor readings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Patient(Base):
    """Synthetic patient demographic and clinical baseline record."""

    __tablename__ = "patients"

    patient_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    age = Column(Integer, nullable=False)
    sex = Column(String(8), nullable=False)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)
    bmi = Column(Float, nullable=False)
    archetype = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    ehr_events = relationship("EHREvent", back_populates="patient", cascade="all, delete-orphan")
    sensor_readings = relationship("SensorReading", back_populates="patient", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")
    notes = relationship("ClinicianNote", back_populates="patient", cascade="all, delete-orphan")


class EHREvent(Base):
    """Discrete longitudinal coded EHR events."""

    __tablename__ = "ehr_events"

    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)  # diagnosis, medication, lab, vitals, family_history
    code = Column(String(64), nullable=False)
    description = Column(String(256), nullable=False)
    value = Column(String(64), nullable=False)
    unit = Column(String(32), nullable=True, default="")
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(64), default="Hospital_EHR")

    patient = relationship("Patient", back_populates="ehr_events")

    __table_args__ = (
        Index("ix_ehr_patient_time", "patient_id", "event_time"),
    )


class SensorReading(Base):
    """Simulated wearable sensor readings and ground-truth home BP cuff readings."""

    __tablename__ = "sensor_readings"

    reading_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(String(64), nullable=False)  # sleep_duration, hrv_rmssd, home_sbp, etc.
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    source = Column(String(64), default="device_stream")

    patient = relationship("Patient", back_populates="sensor_readings")

    __table_args__ = (
        UniqueConstraint("patient_id", "sensor_type", "recorded_at", name="uq_patient_sensor_timestamp"),
        Index("ix_sensor_patient_time", "patient_id", "recorded_at"),
    )


class Prediction(Base):
    """Calibrated probability forecast of next-day hypertensive episode."""

    __tablename__ = "predictions"

    prediction_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    probability = Column(Float, nullable=False)
    risk_level = Column(String(16), nullable=False)  # Low, Moderate, High
    model_version = Column(String(32), default="1.0.0")
    generated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    top_factors = Column(JSON, nullable=False, default=list)
    feature_snapshot = Column(JSON, nullable=False, default=dict)

    patient = relationship("Patient", back_populates="predictions")
    alerts = relationship("Alert", back_populates="prediction")

    __table_args__ = (
        Index("ix_predictions_patient_time", "patient_id", "generated_at"),
    )


class Alert(Base):
    """Clinical decision-support alerts triggered when probability exceeds High threshold."""

    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id = Column(String(64), ForeignKey("predictions.prediction_id", ondelete="SET NULL"), nullable=True)
    risk_level = Column(String(16), nullable=False)  # High
    probability = Column(Float, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    status = Column(String(32), default="open")  # open, acknowledged, snoozed, false_positive
    acknowledged_by = Column(String(128), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    snoozed_until = Column(DateTime(timezone=True), nullable=True, index=True)
    snooze_duration_minutes = Column(Integer, nullable=True)
    snooze_reason = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="alerts")
    prediction = relationship("Prediction", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_patient_time", "patient_id", "created_at"),
    )


class ClinicianNote(Base):
    """Clinician documentation and action logs."""

    __tablename__ = "clinician_notes"

    note_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(String(64), ForeignKey("alerts.alert_id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=False)
    author = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    patient = relationship("Patient", back_populates="notes")


class User(Base):
    """User account for clinician and administrative staff authentication & RBAC."""

    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="clinician")  # clinician, admin, nurse, viewer
    full_name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

