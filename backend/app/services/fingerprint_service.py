"""Sleep Fingerprint and personal baseline deviation service for NightWatch.

Implements the six clinical Sleep Fingerprint axes:
1. Nocturnal BP Stability
2. Autonomic Resilience
3. Sleep Continuity
4. Morning Surge Control
5. Medication Coverage
6. Recovery Capacity

Estimated against each patient's personal 30-day baseline.
"""

from __future__ import annotations

import math
from typing import Any, Dict
from backend.app.schemas import RadarAxisValue, SleepFingerprintData


class FingerprintService:
    """Computes 6-axis normalized radar deviations vs personal 30-day baselines."""

    @staticmethod
    def compute_fingerprint(
        static_dict: Dict[str, Any],
        features_dict: Dict[str, float],
    ) -> SleepFingerprintData:
        """Compute percentage deviations against personal 30-day baseline."""
        # 1. Personal baselines estimated from first 30 days of data (fallback to population reference if unrecorded)
        def _get_val(d: Dict[str, Any], key: str, default: float) -> float:
            v = d.get(key)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return default
            return float(v)

        b_sleep = _get_val(static_dict, "baseline_sleep_hours", 7.0)
        b_hrv = _get_val(static_dict, "baseline_hrv_rmssd", 35.0)
        b_rhr = _get_val(static_dict, "baseline_resting_hr", 68.0)
        b_eff = _get_val(static_dict, "baseline_sleep_efficiency", 0.88)
        b_sbp_std = _get_val(static_dict, "baseline_sbp_std", 3.5)
        b_surge = _get_val(static_dict, "baseline_morning_surge", 3.0)
        b_med = _get_val(static_dict, "baseline_adherence", 1.0)

        # 2. Current observations
        curr_sleep = _get_val(features_dict, "sleep_duration_last_night", b_sleep)
        curr_eff = _get_val(features_dict, "sleep_efficiency_last_night", b_eff)
        curr_hrv = _get_val(features_dict, "hrv_rmssd_last_night", b_hrv)
        curr_rhr = _get_val(features_dict, "resting_hr_last_night", b_rhr)
        curr_sbp_std = _get_val(features_dict, "sbp_std_7d", b_sbp_std)
        curr_surge = _get_val(features_dict, "morning_minus_evening_sbp", b_surge)

        missed_7d = _get_val(features_dict, "missed_doses_7d", 0.0)
        curr_med = max(0.0, 1.0 - (missed_7d / 7.0))

        # 3. Six Clinical Axes Deviations
        # Axis 1: Nocturnal BP Stability (lower variability = higher stability)
        bp_instability = ((curr_sbp_std - b_sbp_std) / max(0.5, b_sbp_std)) * 100.0
        bp_stability_dev = -bp_instability

        # Axis 2: Autonomic Resilience (RMSSD vagal tone buffering)
        hrv_dev = ((curr_hrv - b_hrv) / max(1.0, b_hrv)) * 100.0

        # Axis 3: Sleep Continuity (Efficiency and fragmentation)
        eff_dev = ((curr_eff - b_eff) / max(0.05, b_eff)) * 100.0

        # Axis 4: Morning Surge Control (Surge magnitude control vs personal baseline)
        surge_excess = curr_surge - b_surge
        morning_surge_dev = -((surge_excess / max(1.0, abs(b_surge))) * 100.0)

        # Axis 5: Medication Coverage (Antihypertensive regimen adherence)
        med_coverage_dev = ((curr_med - b_med) / max(0.1, b_med)) * 100.0

        # Axis 6: Recovery Capacity (Sleep duration and restorative sleep relative to personal baseline)
        recovery_dev = ((curr_sleep - b_sleep) / max(1.0, b_sleep)) * 100.0

        # Legacy supporting deviations
        rhr_dev = ((curr_rhr - b_rhr) / max(1.0, b_rhr)) * 100.0

        axes = [
            RadarAxisValue(
                axis="nocturnal_bp_stability",
                display_name="Nocturnal BP Stability",
                baseline_value=round(b_sbp_std, 1),
                current_value=round(curr_sbp_std, 1),
                deviation_pct=round(bp_stability_dev, 1),
                status="adverse" if bp_stability_dev < -25.0 else "normal",
            ),
            RadarAxisValue(
                axis="autonomic_resilience",
                display_name="Autonomic Resilience",
                baseline_value=round(b_hrv, 1),
                current_value=round(curr_hrv, 1),
                deviation_pct=round(hrv_dev, 1),
                status="adverse" if hrv_dev < -20.0 else "normal",
            ),
            RadarAxisValue(
                axis="sleep_continuity",
                display_name="Sleep Continuity",
                baseline_value=round(b_eff * 100.0, 1),
                current_value=round(curr_eff * 100.0, 1),
                deviation_pct=round(eff_dev, 1),
                status="adverse" if eff_dev < -10.0 else "normal",
            ),
            RadarAxisValue(
                axis="morning_surge_control",
                display_name="Morning Surge Control",
                baseline_value=round(b_surge, 1),
                current_value=round(curr_surge, 1),
                deviation_pct=round(morning_surge_dev, 1),
                status="adverse" if morning_surge_dev < -25.0 else "normal",
            ),
            RadarAxisValue(
                axis="medication_coverage",
                display_name="Medication Coverage",
                baseline_value=round(b_med * 100.0, 1),
                current_value=round(curr_med * 100.0, 1),
                deviation_pct=round(med_coverage_dev, 1),
                status="adverse" if med_coverage_dev < -15.0 else "normal",
            ),
            RadarAxisValue(
                axis="recovery_capacity",
                display_name="Recovery Capacity",
                baseline_value=round(b_sleep, 1),
                current_value=round(curr_sleep, 1),
                deviation_pct=round(recovery_dev, 1),
                status="adverse" if recovery_dev < -15.0 else "normal",
            ),
        ]

        adverse_count = sum(1 for a in axes if a.status == "adverse")
        if adverse_count >= 2 or recovery_dev < -25.0 or hrv_dev < -30.0:
            status = "acute_deficit"
        elif adverse_count == 1 or recovery_dev < -10.0 or hrv_dev < -15.0:
            status = "degraded"
        else:
            status = "optimal"

        summary = FingerprintService._generate_summary(
            status=status,
            recovery_dev=recovery_dev,
            curr_sleep=curr_sleep,
            b_sleep=b_sleep,
            hrv_dev=hrv_dev,
            rhr_dev=rhr_dev,
            bp_stability_dev=bp_stability_dev,
            morning_surge_dev=morning_surge_dev,
            med_coverage_dev=med_coverage_dev,
        )

        return SleepFingerprintData(
            nocturnal_bp_stability_pct=round(bp_stability_dev, 1),
            autonomic_resilience_pct=round(hrv_dev, 1),
            sleep_continuity_pct=round(eff_dev, 1),
            morning_surge_control_pct=round(morning_surge_dev, 1),
            medication_coverage_pct=round(med_coverage_dev, 1),
            recovery_capacity_pct=round(recovery_dev, 1),
            sleep_duration_deviation_pct=round(recovery_dev, 1),
            sleep_efficiency_deviation_pct=round(eff_dev, 1),
            hrv_deviation_pct=round(hrv_dev, 1),
            resting_hr_deviation_pct=round(rhr_dev, 1),
            bp_stability_deviation_pct=round(bp_stability_dev, 1),
            nocturnal_dipping_deviation_pct=None,
            axes=axes,
            status=status,
            summary=summary,
        )

    @staticmethod
    def _generate_summary(
        status: str,
        recovery_dev: float,
        curr_sleep: float,
        b_sleep: float,
        hrv_dev: float,
        rhr_dev: float,
        bp_stability_dev: float,
        morning_surge_dev: float,
        med_coverage_dev: float,
    ) -> str:
        """Construct structured clinical summary from baseline deviation metrics."""
        if status == "acute_deficit":
            return (
                f"Significant autonomic and sleep disruption detected. Last night's sleep duration ({curr_sleep:.1f}h) was "
                f"{abs(recovery_dev):.0f}% below personal 30-day baseline ({b_sleep:.1f}h). "
                f"Nocturnal RMSSD HRV shifted {hrv_dev:+.0f}%, accompanied by altered morning surge dynamics "
                f"({morning_surge_dev:+.0f}% control deviation), associated with heightened next-day hypertensive vulnerability."
            )
        elif status == "degraded":
            return (
                f"Mild circadian strain observed. Sleep duration is {abs(recovery_dev):.0f}% below personal baseline, "
                f"with a {abs(hrv_dev):.0f}% reduction in vagal HRV tone. Blood pressure variability indicates "
                f"sub-optimal autonomic dampening. Ongoing trend monitoring recommended."
            )
        else:
            return (
                f"Autonomic and sleep metrics remain well-aligned with personal 30-day baseline. "
                f"Sleep duration ({curr_sleep:.1f}h, {recovery_dev:+.0f}%) and RMSSD HRV ({hrv_dev:+.0f}%) "
                f"demonstrate stable cardiovascular buffer capacity and preserved diurnal control."
            )
