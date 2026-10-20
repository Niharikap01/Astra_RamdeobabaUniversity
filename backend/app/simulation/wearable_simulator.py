"""Wearable and Home BP Cuff Longitudinal Simulator for NightWatch.

Simulates 120 days of multi-modal physiological context (sleep stages, HRV, resting HR,
physical activity, medication adherence) and ground-truth home BP cuff readings.
Enforces circadian coupling, latent hemodynamic risk accumulation, and next-day
hypertensive episode labeling (next-day SBP >= 140 or DBP >= 90 mmHg).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .ehr_simulator import PatientProfile


@dataclass
class DailySimulationRecord:
    """Consolidated daily physiological measurement and event state for a patient."""

    patient_id: str
    day_index: int
    date: str
    sleep_duration_hours: float
    deep_sleep_hours: float
    rem_sleep_hours: float
    awakenings_count: int
    sleep_efficiency: float
    hrv_rmssd: float
    resting_hr: float
    steps: int
    active_minutes: int
    medication_taken: int
    stress_level: float  # 0.0 to 1.0 proxy
    morning_sbp: float
    morning_dbp: float
    evening_sbp: float
    evening_dbp: float
    latent_risk_score: float
    hypertensive_episode_next_day: int | str = 0  # Last day is explicitly unlabelled because no next-day cuff exists.
    lead_time_hours: float = 0.0  # Alert lead time hours prior to surge onset

    def to_sensor_readings(self, base_datetime: datetime) -> List[Dict[str, Any]]:
        """Deconstruct into individual timestamped sensor readings for database ingestion."""
        readings: List[Dict[str, Any]] = []
        rec_date = base_datetime + timedelta(days=self.day_index)
        t_sleep = rec_date.replace(hour=7, minute=0, second=0, microsecond=0)
        t_morning_bp = rec_date.replace(hour=8, minute=0, second=0, microsecond=0)
        t_day_wearable = rec_date.replace(hour=18, minute=0, second=0, microsecond=0)
        t_evening_bp = rec_date.replace(hour=20, minute=30, second=0, microsecond=0)
        t_med = rec_date.replace(hour=21, minute=0, second=0, microsecond=0)

        def add_reading(stype: str, val: float, unit: str, ts: datetime, src: str):
            readings.append({
                "patient_id": self.patient_id,
                "sensor_type": stype,
                "value": round(val, 2),
                "unit": unit,
                "recorded_at": ts.isoformat(),
                "ingested_at": ts.isoformat(),
                "source": src,
            })

        # Sleep & Autonomic context (Smart Ring / Watch)
        add_reading("sleep_duration", self.sleep_duration_hours, "hours", t_sleep, "wearable_tracker")
        add_reading("deep_sleep", self.deep_sleep_hours, "hours", t_sleep, "wearable_tracker")
        add_reading("rem_sleep", self.rem_sleep_hours, "hours", t_sleep, "wearable_tracker")
        add_reading("awakenings", float(self.awakenings_count), "count", t_sleep, "wearable_tracker")
        add_reading("sleep_efficiency", self.sleep_efficiency, "ratio", t_sleep, "wearable_tracker")
        add_reading("hrv_rmssd", self.hrv_rmssd, "ms", t_sleep, "wearable_tracker")
        add_reading("resting_hr", self.resting_hr, "bpm", t_sleep, "wearable_tracker")

        # Daytime activity
        add_reading("steps", float(self.steps), "steps", t_day_wearable, "wearable_tracker")

        # Medication adherence record
        add_reading("medication_taken", float(self.medication_taken), "binary", t_med, "smart_pillbox")

        # Ground truth home BP cuff readings (morning + evening)
        add_reading("home_sbp", self.morning_sbp, "mmHg", t_morning_bp, "home_bp_cuff")
        add_reading("home_dbp", self.morning_dbp, "mmHg", t_morning_bp, "home_bp_cuff")
        add_reading("home_sbp", self.evening_sbp, "mmHg", t_evening_bp, "home_bp_cuff")
        add_reading("home_dbp", self.evening_dbp, "mmHg", t_evening_bp, "home_bp_cuff")

        return readings


class WearableSimulator:
    """Longitudinal multi-modal wearable & home BP simulator with clinical archetype fidelity."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def simulate_patient_history(
        self,
        profile: PatientProfile,
        days: int = 120,
        start_date: Optional[datetime] = None,
    ) -> List[DailySimulationRecord]:
        """Simulate a continuous daily longitudinal record sequence for a patient."""
        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

        records: List[DailySimulationRecord] = []

        # Internal state trackers for autoregressive drift
        accumulated_sleep_debt = 0.0
        missed_dose_streak = 0

        for d in range(days):
            current_date = start_date + timedelta(days=d)
            is_weekend = current_date.weekday() >= 5

            # 1. Sleep simulation conditioned on archetype & weekend
            sleep_hours, deep_h, rem_h, awakenings, efficiency = self._simulate_sleep(
                profile, is_weekend, d
            )

            # Sleep debt tracking (relative to personal baseline)
            daily_debt = max(-1.0, min(3.0, profile.baseline_sleep_hours - sleep_hours))
            accumulated_sleep_debt = 0.70 * accumulated_sleep_debt + 0.30 * max(0.0, daily_debt)

            # 2. HRV and Resting HR (inversely coupled with sleep quality, debt, and stress)
            stress_level = float(np.clip(self.rng.beta(2, 5) + (0.2 if sleep_hours < 5.5 else 0.0), 0.0, 1.0))
            hrv_rmssd, resting_hr = self._simulate_autonomic(profile, sleep_hours, efficiency, stress_level)

            # 3. Daytime physical activity (steps and active minutes)
            steps, active_min = self._simulate_activity(profile, is_weekend, sleep_hours)

            # 4. Medication adherence
            med_taken, missed_dose_streak = self._simulate_adherence(profile, missed_dose_streak)

            # 5. Latent blood pressure risk score synthesis
            latent_risk, m_sbp, m_dbp, e_sbp, e_dbp = self._simulate_hemodynamics(
                profile=profile,
                sleep_hours=sleep_hours,
                efficiency=efficiency,
                accumulated_sleep_debt=accumulated_sleep_debt,
                hrv=hrv_rmssd,
                resting_hr=resting_hr,
                steps=steps,
                med_taken=med_taken,
                missed_streak=missed_dose_streak,
                stress_level=stress_level,
            )

            rec = DailySimulationRecord(
                patient_id=profile.patient_id,
                day_index=d,
                date=current_date.strftime("%Y-%m-%d"),
                sleep_duration_hours=round(sleep_hours, 2),
                deep_sleep_hours=round(deep_h, 2),
                rem_sleep_hours=round(rem_h, 2),
                awakenings_count=awakenings,
                sleep_efficiency=round(efficiency, 3),
                hrv_rmssd=round(hrv_rmssd, 1),
                resting_hr=round(resting_hr, 1),
                steps=steps,
                active_minutes=active_min,
                medication_taken=med_taken,
                stress_level=round(stress_level, 2),
                morning_sbp=round(m_sbp, 1),
                morning_dbp=round(m_dbp, 1),
                evening_sbp=round(e_sbp, 1),
                evening_dbp=round(e_dbp, 1),
                latent_risk_score=round(latent_risk, 3),
                hypertensive_episode_next_day=0,
            )
            records.append(rec)

        # Label next-day hypertensive episode (SBP >= 140 or DBP >= 90) with physiological lead time
        for i in range(len(records) - 1):
            next_rec = records[i + 1]
            morning_excursion = (next_rec.morning_sbp >= 140.0 or next_rec.morning_dbp >= 90.0)
            evening_excursion = (next_rec.evening_sbp >= 140.0 or next_rec.evening_dbp >= 90.0)
            is_htn_episode = int(morning_excursion or evening_excursion)
            records[i].hypertensive_episode_next_day = is_htn_episode
            # Lead time in hours from prior-day alert evaluation (21:00) to episode onset (08:00 or 20:30 next day)
            records[i].lead_time_hours = 11.0 if morning_excursion else (23.5 if evening_excursion else 0.0)

        # No next-day cuff reading exists for the final day, so its outcome is unlabelled.
        records[-1].hypertensive_episode_next_day = "unlabelled"
        return records

    def _simulate_sleep(
        self, profile: PatientProfile, is_weekend: bool, day_idx: int
    ) -> Tuple[float, float, float, int, float]:
        """Simulate sleep duration and architecture."""
        archetype = profile.archetype
        base_h = profile.baseline_sleep_hours
        weekend_boost = 0.4 if is_weekend else 0.0

        if archetype == "poor_sleep_risk":
            noise = float(self.rng.normal(0.0, 0.6))
            sleep_h = max(3.5, min(7.5, base_h + weekend_boost + noise))
            deep_ratio = float(np.clip(self.rng.normal(0.11, 0.02), 0.05, 0.18))
            rem_ratio = float(np.clip(self.rng.normal(0.16, 0.03), 0.08, 0.22))
            awakenings = int(np.clip(self.rng.poisson(4.8), 2, 10))
            efficiency = float(np.clip(self.rng.normal(0.74, 0.05), 0.55, 0.88))
        elif archetype == "osa_suspected":
            noise = float(self.rng.normal(0.0, 0.7))
            sleep_h = max(4.0, min(8.0, base_h + weekend_boost + noise))
            deep_ratio = float(np.clip(self.rng.normal(0.09, 0.02), 0.04, 0.15))
            rem_ratio = float(np.clip(self.rng.normal(0.14, 0.03), 0.06, 0.20))
            awakenings = int(np.clip(self.rng.poisson(6.2), 3, 12))
            efficiency = float(np.clip(self.rng.normal(0.70, 0.06), 0.50, 0.85))
        elif archetype == "well_controlled":
            noise = float(self.rng.normal(0.0, 0.35))
            sleep_h = max(6.5, min(9.2, base_h + weekend_boost + noise))
            deep_ratio = float(np.clip(self.rng.normal(0.19, 0.02), 0.13, 0.26))
            rem_ratio = float(np.clip(self.rng.normal(0.22, 0.02), 0.15, 0.28))
            awakenings = int(np.clip(self.rng.poisson(1.3), 0, 4))
            efficiency = float(np.clip(self.rng.normal(0.91, 0.03), 0.82, 0.98))
        else:
            noise = float(self.rng.normal(0.0, 0.45))
            sleep_h = max(5.0, min(8.8, base_h + weekend_boost + noise))
            deep_ratio = float(np.clip(self.rng.normal(0.16, 0.02), 0.10, 0.22))
            rem_ratio = float(np.clip(self.rng.normal(0.19, 0.02), 0.12, 0.25))
            awakenings = int(np.clip(self.rng.poisson(2.4), 0, 6))
            efficiency = float(np.clip(self.rng.normal(0.85, 0.04), 0.72, 0.94))

        deep_h = sleep_h * deep_ratio
        rem_h = sleep_h * rem_ratio
        return sleep_h, deep_h, rem_h, awakenings, efficiency

    def _simulate_autonomic(
        self, profile: PatientProfile, sleep_hours: float, efficiency: float, stress: float
    ) -> Tuple[float, float]:
        """Simulate RMSSD HRV and resting heart rate with autonomic balance."""
        base_hrv = profile.baseline_hrv_rmssd
        base_rhr = profile.baseline_resting_hr

        # Sleep deficit or poor efficiency decreases HRV and elevates resting HR
        sleep_delta = sleep_hours - profile.baseline_sleep_hours
        hrv_sleep_effect = sleep_delta * 2.8 + (efficiency - 0.85) * 15.0
        hrv_stress_effect = -stress * 8.0
        noise_hrv = float(self.rng.normal(0.0, 2.5))
        simulated_hrv = max(8.0, min(110.0, base_hrv + hrv_sleep_effect + hrv_stress_effect + noise_hrv))

        rhr_sleep_effect = -sleep_delta * 1.5 - (efficiency - 0.85) * 8.0
        rhr_stress_effect = stress * 6.5
        noise_rhr = float(self.rng.normal(0.0, 1.8))
        simulated_rhr = max(45.0, min(105.0, base_rhr + rhr_sleep_effect + rhr_stress_effect + noise_rhr))

        return simulated_hrv, simulated_rhr

    def _simulate_activity(
        self, profile: PatientProfile, is_weekend: bool, sleep_hours: float
    ) -> Tuple[int, int]:
        """Simulate daytime steps and active minutes."""
        archetype = profile.archetype
        if archetype == "sedentary_high_risk":
            base_steps = 2600
        elif archetype == "well_controlled":
            base_steps = 8800
        elif archetype == "poor_sleep_risk":
            base_steps = 4500
        else:
            base_steps = 6200

        fatigue_penalty = -600 if sleep_hours < 5.5 else (400 if sleep_hours > 7.5 else 0)
        weekend_shift = 800 if (is_weekend and archetype != "sedentary_high_risk") else -200
        steps = int(max(800, self.rng.normal(base_steps + fatigue_penalty + weekend_shift, 1100)))
        active_min = int(max(10, steps // 110 + self.rng.integers(-5, 10)))
        return steps, active_min

    def _simulate_adherence(
        self, profile: PatientProfile, streak: int
    ) -> Tuple[int, int]:
        """Simulate oral antihypertensive medication intake."""
        archetype = profile.archetype
        if archetype == "well_controlled":
            prob_take = 0.98
        elif archetype == "controlled_hypertensive":
            prob_take = 0.94
        elif archetype == "non_adherent":
            prob_take = 0.58 if streak == 0 else 0.40  # inertia when missed
        elif archetype == "poor_sleep_risk":
            prob_take = 0.88
        else:
            prob_take = 0.82

        taken = 1 if self.rng.random() < prob_take else 0
        new_streak = 0 if taken else streak + 1
        return taken, new_streak

    def _simulate_hemodynamics(
        self,
        profile: PatientProfile,
        sleep_hours: float,
        efficiency: float,
        accumulated_sleep_debt: float,
        hrv: float,
        resting_hr: float,
        steps: int,
        med_taken: int,
        missed_streak: int,
        stress_level: float,
        sodium_proxy: Optional[float] = None,
    ) -> Tuple[float, float, float, float, float]:
        """Synthesize latent risk score and resulting morning/evening SBP and DBP.
        Latent risk and acute hemodynamic surge depend on prior-night sleep debt,
        low HRV relative to personal baseline, missed doses, sedentary behavior,
        and dietary sodium / acute psychosocial stress proxy.
        """
        # EHR static risk contribution
        ehr_risk = (
            (profile.baseline_sbp - 124.0) * 0.015
            + profile.diabetes * 0.05
            + profile.ckd * 0.06
            + profile.osa * 0.06
            + (profile.bmi - 27.0) * 0.008
            + (profile.age - 55.0) * 0.003
        )

        # Context risk: prior-night sleep debt & poor efficiency
        sleep_risk = max(0.0, min(0.50, accumulated_sleep_debt * 0.16 + max(0.0, 0.85 - efficiency) * 0.70))

        # Autonomic risk: low HRV relative to personal baseline (vagal withdrawal)
        base_hrv = max(10.0, profile.baseline_hrv_rmssd)
        hrv_relative_drop = max(0.0, min(1.0, (base_hrv - hrv) / base_hrv))
        hrv_risk = hrv_relative_drop * 0.32

        # Physical activity: sedentary penalty vs protective active movement
        sedentary = steps < 3500
        active = steps > 8500
        sedentary_risk = 0.08 if sedentary else (-0.04 if active else 0.0)

        # Sodium & psychosocial stress proxy
        if sodium_proxy is None:
            sodium_proxy = float(np.clip(stress_level * 0.70 + self.rng.beta(2, 4) * 0.40, 0.0, 1.0))
        stress_risk = (sodium_proxy - 0.32) * 0.16

        # Medication adherence effect (loss of vascular protection)
        adherence_risk = 0.0
        if not med_taken:
            adherence_risk = 0.26 + min(0.24, missed_streak * 0.10)

        # Total latent risk probability [0, 1]
        latent_z = -2.20 + ehr_risk + sleep_risk + hrv_risk + sedentary_risk + stress_risk + adherence_risk
        latent_prob = 1.0 / (1.0 + np.exp(-latent_z))

        # Dynamic acute hemodynamic surges added to resting baseline
        sbp_surge = (
            sleep_risk * 16.0
            + hrv_risk * 14.0
            + adherence_risk * 20.0
            + (5.5 if sedentary else 0.0)
            + max(0.0, stress_risk) * 9.0
        )
        dbp_surge = (
            sleep_risk * 9.0
            + hrv_risk * 8.0
            + adherence_risk * 12.0
            + (3.0 if sedentary else 0.0)
            + max(0.0, stress_risk) * 5.0
        )

        morning_surge = 2.0 + (3.5 if (profile.osa or sleep_hours < 5.5) else 0.0)
        m_sbp = max(90.0, self.rng.normal(profile.baseline_sbp + sbp_surge + morning_surge, 3.5))
        m_dbp = max(55.0, self.rng.normal(profile.baseline_dbp + dbp_surge + morning_surge * 0.6, 2.5))
        e_sbp = max(90.0, self.rng.normal(profile.baseline_sbp + sbp_surge * 0.82, 3.5))
        e_dbp = max(55.0, self.rng.normal(profile.baseline_dbp + dbp_surge * 0.82, 2.5))

        return latent_prob, m_sbp, m_dbp, e_sbp, e_dbp
