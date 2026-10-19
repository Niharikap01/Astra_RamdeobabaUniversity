"""Alert generation, deduplication, and clinician action service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.config import settings
from backend.app.models import Alert, ClinicianNote, Prediction

logger = logging.getLogger("nightwatch.alerts")


class AlertService:
    """Manages clinical alerts with deduplication cooldown and review actions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_and_expire_snoozes(self, patient_id: Optional[str] = None) -> int:
        """Expire snoozed alerts whose snooze window has lapsed, reverting status to 'open'."""
        now = datetime.now(timezone.utc)
        stmt = select(Alert).where(
            Alert.status == "snoozed",
            Alert.snoozed_until.is_not(None),
            Alert.snoozed_until <= now,
        )
        if patient_id:
            stmt = stmt.where(Alert.patient_id == patient_id)

        expired_alerts = list(self.db.execute(stmt).scalars().all())
        for a in expired_alerts:
            a.status = "open"
            a.snoozed_until = None
            logger.info(f"Snooze expired for alert {a.alert_id} (patient {a.patient_id}). Reverted status to open.")

        if expired_alerts:
            self.db.commit()
        return len(expired_alerts)

    def evaluate_and_create_alert(
        self,
        patient_id: str,
        prediction: Prediction,
    ) -> Optional[Alert]:
        """Trigger an alert if probability >= high threshold and not in cooldown."""
        if prediction.probability < settings.risk_threshold_high:
            return None

        # Expire any lapsed snoozes first
        self.check_and_expire_snoozes(patient_id)

        # Cooldown check: account for open, acknowledged, and snoozed alerts
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.alert_cooldown_hours)
        now_utc = datetime.now(timezone.utc)
        recent_alert = self.db.execute(
            select(Alert).where(
                Alert.patient_id == patient_id,
                (Alert.created_at >= cooldown_cutoff) | (Alert.snoozed_until > now_utc),
                Alert.status.in_(["open", "acknowledged", "snoozed"]),
            )
        ).scalars().first()

        if recent_alert:
            logger.info(
                f"Suppressed duplicate alert for patient {patient_id} within cooldown/snooze window "
                f"(recent alert {recent_alert.alert_id} has status '{recent_alert.status}')."
            )
            return None

        # Generate clinician-oriented alert message
        top_driver = ""
        if prediction.top_factors and len(prediction.top_factors) > 0:
            first_factor = prediction.top_factors[0]
            top_driver = f" Primary driver: {first_factor.get('display_name', 'Hemodynamic volatility')} ({first_factor.get('reason', '')})"

        message = (
            f"HIGH RISK ALERT: Predicted 24-hour hypertensive episode probability is {prediction.probability:.1%}."
            f"{top_driver} Clinician review and home blood pressure recheck recommended."
        )

        alert = Alert(
            patient_id=patient_id,
            prediction_id=prediction.prediction_id,
            risk_level="High",
            probability=prediction.probability,
            message=message,
            created_at=datetime.now(timezone.utc),
            status="open",
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.warning(f"New High Risk Alert generated: {alert.alert_id} for patient {patient_id}")
        return alert

    def get_patient_alerts(self, patient_id: str, limit: int = 50) -> List[Alert]:
        """Fetch alert feed for patient after expiring lapsed snoozes."""
        self.check_and_expire_snoozes(patient_id)
        return list(self.db.execute(
            select(Alert)
            .where(Alert.patient_id == patient_id)
            .order_by(desc(Alert.created_at))
            .limit(limit)
        ).scalars().all())

    def acknowledge_alert(
        self,
        alert_id: str,
        clinician_name: str = "Dr. Clinician",
        comment: Optional[str] = None,
    ) -> Optional[Alert]:
        """Mark an open alert as acknowledged."""
        alert = self.db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_by = clinician_name
        alert.acknowledged_at = datetime.now(timezone.utc)

        if comment:
            note = ClinicianNote(
                patient_id=alert.patient_id,
                alert_id=alert.alert_id,
                note=f"[Alert Acknowledged by {clinician_name}] {comment}",
                author=clinician_name,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(note)

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def snooze_alert(
        self,
        alert_id: str,
        clinician_name: str = "Dr. Clinician",
        snooze_hours: float = 4.0,
        reason: Optional[str] = None,
    ) -> Optional[Alert]:
        if not reason or not reason.strip():
            raise ValueError("A documented clinical reason is required to snooze an alert.")

        alert = self.db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if not alert:
            return None

        now = datetime.now(timezone.utc)
        duration_minutes = int(snooze_hours * 60)
        snoozed_until = now + timedelta(minutes=duration_minutes)

        alert.status = "snoozed"
        alert.acknowledged_by = clinician_name
        alert.acknowledged_at = now
        alert.snooze_duration_minutes = duration_minutes
        alert.snoozed_until = snoozed_until
        alert.snooze_reason = reason

        reason_str = f" Reason: {reason}" if reason else ""
        note = ClinicianNote(
            patient_id=alert.patient_id,
            alert_id=alert.alert_id,
            note=f"[Alert Snoozed for {snooze_hours:.1f}h by {clinician_name}]{reason_str}",
            author=clinician_name,
            created_at=now,
        )
        self.db.add(note)

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def mark_false_positive(
        self,
        alert_id: str,
        clinician_name: str = "Dr. Clinician",
        reason: str = "Situational anomaly",
    ) -> Optional[Alert]:
        """Mark alert as false positive for model audit."""
        alert = self.db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if not alert:
            return None

        alert.status = "false_positive"
        alert.acknowledged_by = clinician_name
        alert.acknowledged_at = datetime.now(timezone.utc)

        note = ClinicianNote(
            patient_id=alert.patient_id,
            alert_id=alert.alert_id,
            note=f"[Marked False Positive by {clinician_name}] Reason: {reason}",
            author=clinician_name,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(note)

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def add_clinician_note(
        self,
        patient_id: str,
        note_text: str,
        alert_id: Optional[str] = None,
        author: Optional[str] = "Dr. Clinician",
    ) -> ClinicianNote:
        """Add clinical documentation note."""
        note = ClinicianNote(
            patient_id=patient_id,
            alert_id=alert_id,
            note=note_text,
            author=author,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note
