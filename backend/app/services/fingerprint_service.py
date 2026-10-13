"""Sleep Fingerprint and personal baseline deviation service for NightWatch."""

from __future__ import annotations

from typing import Any, Dict
from backend.app.schemas import RadarAxisValue, SleepFingerprintData


class FingerprintService:
    """Computes 5-axis normalized radar deviations vs personal 30-day baselines."""

    @staticmethod
    def compute_fingerprint(
        static_dict: Dict[str, Any],
        features_dict: Dict[str, float],
    ) -> SleepFingerprintData:
        """Compute percentage deviations against personal 30-day baseline."""
        b_sleep = float(static_dict.get("baseline_sleep_hours", 7.0))
        b_hrv = float(static_dict.get("baseline_hrv_rmssd", 35.0))
        b_rhr = float(static_dict.get("baseline_resting_hr", 68.0))
        b_eff = 0.88

        curr_sleep = features_dict.get("sleep_duration_last_night", b_sleep)
        curr_eff = features_dict.get("sleep_efficiency_last_night", b_eff)
        curr_hrv = features_dict.get("hrv_rmssd_last_night", b_hrv)
        curr_rhr = features_dict.get("resting_hr_last_night", b_rhr)
        curr_sbp_std = features_dict.get("sbp_std_7d", 3.5)

        # Deviations in percentage [-100%, +100%]
        sleep_dev = ((curr_sleep - b_sleep) / b_sleep) * 100.0
        eff_dev = ((curr_eff - b_eff) / b_eff) * 100.0
        hrv_dev = ((curr_hrv - b_hrv) / b_hrv) * 100.0
        rhr_dev = ((curr_rhr - b_rhr) / b_rhr) * 100.0
        # BP stability: deviation from standard stable target variability (3.2 mmHg)
        bp_instability = ((curr_sbp_std - 3.2) / 3.2) * 100.0
        bp_stability_dev = -bp_instability  # Higher is more stable

        # 6th Axis: Nocturnal dipping percentage (expected healthy dipping is 10-20% drop during sleep)
        # Deviation vs target healthy 15% nocturnal dip
        morning_sbp = features_dict.get("morning_sbp_mean_7d", 128.0)
        evening_sbp = features_dict.get("evening_sbp_mean_7d", 122.0)
        est_dipping_pct = max(-5.0, min(25.0, ((evening_sbp - morning_sbp * 0.90) / morning_sbp) * 100.0))
        dipping_dev = ((est_dipping_pct - 12.0) / 12.0) * 100.0

        # Detailed 6-axis structured list for radar chart
        axes = [
            RadarAxisValue(
                axis="sleep_duration",
                display_name="Sleep Duration",
                baseline_value=round(b_sleep, 1),
                current_value=round(curr_sleep, 1),
                deviation_pct=round(sleep_dev, 1),
                status="adverse" if sleep_dev < -15 else "normal",
            ),
            RadarAxisValue(
                axis="sleep_efficiency",
                display_name="Sleep Efficiency",
                baseline_value=round(b_eff * 100, 1),
                current_value=round(curr_eff * 100, 1),
                deviation_pct=round(eff_dev, 1),
                status="adverse" if eff_dev < -10 else "normal",
            ),
            RadarAxisValue(
                axis="hrv_rmssd",
                display_name="RMSSD HRV",
                baseline_value=round(b_hrv, 1),
                current_value=round(curr_hrv, 1),
                deviation_pct=round(hrv_dev, 1),
                status="adverse" if hrv_dev < -20 else "normal",
            ),
            RadarAxisValue(
                axis="resting_hr",
                display_name="Resting HR",
                baseline_value=round(b_rhr, 1),
                current_value=round(curr_rhr, 1),
                deviation_pct=round(rhr_dev, 1),
                status="adverse" if rhr_dev > 10 else "normal",
            ),
            RadarAxisValue(
                axis="bp_stability",
                display_name="BP Stability",
                baseline_value=3.2,
                current_value=round(curr_sbp_std, 1),
                deviation_pct=round(bp_stability_dev, 1),
                status="adverse" if bp_stability_dev < -25 else "normal",
            ),
            RadarAxisValue(
                axis="nocturnal_dipping",
                display_name="Nocturnal Dipping",
                baseline_value=12.0,
                current_value=round(est_dipping_pct, 1),
                deviation_pct=round(dipping_dev, 1),
                status="adverse" if est_dipping_pct < 5.0 else "normal",
            ),
        ]

        # Determine clinical autonomic status
        if sleep_dev < -25.0 or hrv_dev < -30.0 or rhr_dev > 15.0 or est_dipping_pct < 0.0:
            status = "acute_deficit"
        elif sleep_dev < -10.0 or hrv_dev < -15.0 or rhr_dev > 8.0 or est_dipping_pct < 8.0:
            status = "degraded"
        else:
            status = "optimal"

        summary = FingerprintService._generate_summary(
            status=status,
            sleep_dev=sleep_dev,
            curr_sleep=curr_sleep,
            b_sleep=b_sleep,
            hrv_dev=hrv_dev,
            rhr_dev=rhr_dev,
            bp_stability_dev=bp_stability_dev,
        )

        return SleepFingerprintData(
            sleep_duration_deviation_pct=round(sleep_dev, 1),
            sleep_efficiency_deviation_pct=round(eff_dev, 1),
            hrv_deviation_pct=round(hrv_dev, 1),
            resting_hr_deviation_pct=round(rhr_dev, 1),
            bp_stability_deviation_pct=round(bp_stability_dev, 1),
            nocturnal_dipping_deviation_pct=round(dipping_dev, 1),
            axes=axes,
            status=status,
            summary=summary,
        )

    @staticmethod
    def _generate_summary(
        status: str,
        sleep_dev: float,
        curr_sleep: float,
        b_sleep: float,
        hrv_dev: float,
        rhr_dev: float,
        bp_stability_dev: float,
    ) -> str:
        """Construct structured clinical summary from baseline deviation metrics."""
        if status == "acute_deficit":
            return (
                f"Severe autonomic disruption detected. Last night's sleep duration ({curr_sleep:.1f}h) was "
                f"{abs(sleep_dev):.0f}% below personal baseline ({b_sleep:.1f}h). "
                f"Nocturnal RMSSD HRV dropped {abs(hrv_dev):.0f}%, accompanied by elevated resting heart rate "
                f"(+{rhr_dev:.0f}%), consistent with acute sympathetic overdrive and morning hypertensive surge risk."
            )
        elif status == "degraded":
            return (
                f"Mild-to-moderate circadian strain observed. Sleep duration is {abs(sleep_dev):.0f}% below baseline, "
                f"with a {abs(hrv_dev):.0f}% reduction in vagal HRV tone. Blood pressure variability indicates "
                f"sub-optimal autonomic dampening. Trend review recommended."
            )
        else:
            return (
                f"Autonomic and sleep metrics remain well-aligned with personal baseline. "
                f"Sleep duration ({curr_sleep:.1f}h, {sleep_dev:+.0f}%) and RMSSD HRV ({hrv_dev:+.0f}%) "
                f"demonstrate preserved nocturnal dipping and cardiovascular buffer capacity."
            )
