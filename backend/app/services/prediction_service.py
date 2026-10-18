"""Prediction and ML inference service for NightWatch."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import Prediction
from backend.app.schemas import PredictionResponse, TopFactor
from ml.explain import ModelExplainer

logger = logging.getLogger("nightwatch.prediction")


class PredictionService:
    """Manages calibrated model loading, live inference scoring, and SHAP explainability."""

    _model: Optional[Any] = None
    _calibrator: Optional[Any] = None
    _feature_names: Optional[List[str]] = None
    _explainer: Optional[ModelExplainer] = None
    _model_version: str = "1.1.0"

    def __init__(self, db: Session) -> None:
        self.db = db
        self._ensure_model_loaded()

    @classmethod
    def is_model_loaded(cls) -> bool:
        """Check whether the ML model, calibrator, and feature names are loaded."""
        return cls._model is not None and cls._calibrator is not None and cls._feature_names is not None

    @classmethod
    def _ensure_model_loaded(cls) -> None:
        """Load serialized LightGBM and calibrator artifacts; trigger automated training if missing."""
        if cls._model is not None and cls._calibrator is not None:
            return

        model_path = os.path.join(settings.ml_artifacts_dir, "lightgbm_model.joblib")
        calibrator_path = os.path.join(settings.ml_artifacts_dir, "calibrator.joblib")
        features_path = os.path.join(settings.ml_artifacts_dir, "feature_names.json")

        if not (os.path.exists(model_path) and os.path.exists(calibrator_path) and os.path.exists(features_path)):
            logger.warning("ML artifacts not found. Initiating automated model training and calibration...")
            from ml.train_lightgbm import LightGBMTrainer
            from pathlib import Path
            trainer = LightGBMTrainer(
                artifacts_dir=settings.ml_artifacts_dir,
                data_dir=str(Path(settings.data_dir) / "processed"),
                docs_dir=settings.docs_dir,
            )
            trainer.run_full_pipeline(force_regenerate=True)

        try:
            cls._model = joblib.load(model_path)
            cls._calibrator = joblib.load(calibrator_path)
            with open(features_path, "r") as f:
                cls._feature_names = json.load(f)

            version_path = os.path.join(settings.ml_artifacts_dir, "model_version.txt")
            if os.path.exists(version_path):
                with open(version_path, "r") as f:
                    cls._model_version = f.read().strip()

            cls._explainer = ModelExplainer(cls._model, cls._feature_names)
            logger.info(f"Loaded NightWatch calibrated model v{cls._model_version} with {len(cls._feature_names)} features.")
        except Exception as e:
            logger.error(f"Failed to load ML artifacts: {e}", exc_info=True)
            raise RuntimeError(f"Unable to initialize ML model artifacts: {e}")

    def compute_confidence(
        self,
        prob: float,
        coverage_pct: Optional[float] = None,
    ) -> Tuple[float, List[float]]:
        """Alias for compute_uncertainty_range required by honest-data-layer tests."""
        return self.compute_uncertainty_range(prob, coverage_pct=coverage_pct)

    def compute_uncertainty_range(
        self,
        prob: float,
        coverage_pct: Optional[float] = None,
    ) -> Tuple[float, List[float]]:
        """Coverage-adjusted uncertainty range (heuristic).

        NOT a statistical confidence interval. This is a deterministic
        heuristic that widens the displayed uncertainty band when sensor
        coverage is low. See docs/clinical_safety.md for the exact formula.

        Returns:
            (quality_score, [lower_bound, upper_bound])
            quality_score: 0-1 heuristic data-quality indicator.
            lower_bound / upper_bound: probability ± coverage-scaled margin.
        """
        import math
        cov = coverage_pct if coverage_pct is not None else 100.0
        cov_ratio = max(0.1, min(1.0, cov / 100.0))
        margin = round(min(0.25, 0.08 / math.sqrt(cov_ratio)), 4)
        quality_score = round(max(0.1, min(1.0, cov_ratio * (1.0 - 0.2 * abs(prob - 0.5)))), 3)
        lower = max(0.0, round(prob - margin, 4))
        upper = min(1.0, round(prob + margin, 4))
        return quality_score, [lower, upper]

    def score_features(
        self,
        features_dict: Dict[str, float],
    ) -> Tuple[float, str, List[Dict[str, Any]]]:
        """Compute calibrated probability, risk tier, and top clinical drivers."""
        assert self._feature_names is not None
        assert self._calibrator is not None

        x_row = np.array([[features_dict.get(k, float("nan")) for k in self._feature_names]], dtype=float)
        prob = float(self._calibrator.predict_proba(x_row)[0, 1])

        # Clinical Risk Band classification
        if prob >= settings.risk_threshold_high:
            risk_level = "High"
        elif prob >= settings.risk_threshold_moderate:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        # Explainability
        top_factors = []
        if self._explainer is not None:
            top_factors = self._explainer.explain_instance(features_dict, top_k=5)

        return round(prob, 4), risk_level, top_factors

    def generate_and_save_prediction(
        self,
        patient_id: str,
        features_dict: Dict[str, float],
        enforce_coverage: bool = True,
    ) -> Prediction:
        """Score patient feature vector and persist to predictions table with coverage-aware confidence."""
        from backend.app.services.fusion_service import FusionService
        from backend.app.models import SensorReading
        from sqlalchemy import select

        fusion_svc = FusionService(self.db)
        overall_cov, _ = fusion_svc.compute_data_coverage(patient_id, days_lookback=7)

        if enforce_coverage and overall_cov < (settings.min_coverage_threshold * 100.0):
            # Check if patient has any readings at all in the DB
            any_reading = self.db.execute(
                select(SensorReading).where(SensorReading.patient_id == patient_id)
            ).scalars().first()
            if any_reading is not None:
                raise ValueError(
                    f"Prediction refused: Data coverage ({overall_cov:.1f}%) is below minimum threshold "
                    f"({settings.min_coverage_threshold * 100.0:.1f}%)."
                )

        prob, risk_level, top_factors = self.score_features(features_dict)
        conf_score, conf_interval = self.compute_uncertainty_range(prob, coverage_pct=overall_cov)

        snapshot = dict(features_dict)
        snapshot["_data_coverage_pct"] = overall_cov
        snapshot["_confidence_score"] = conf_score
        snapshot["_confidence_lower"] = conf_interval[0]
        snapshot["_confidence_upper"] = conf_interval[1]

        pred_record = Prediction(
            patient_id=patient_id,
            probability=prob,
            risk_level=risk_level,
            model_version=self._model_version,
            generated_at=datetime.now(timezone.utc),
            top_factors=top_factors,
            feature_snapshot=snapshot,
        )
        self.db.add(pred_record)
        self.db.commit()
        self.db.refresh(pred_record)
        return pred_record

    def get_latest_prediction(self, patient_id: str) -> Optional[Prediction]:
        """Retrieve most recent prediction record for patient."""
        from sqlalchemy import select, desc
        return self.db.execute(
            select(Prediction)
            .where(Prediction.patient_id == patient_id)
            .order_by(desc(Prediction.generated_at))
        ).scalars().first()

    def get_prediction_history(self, patient_id: str, limit: int = 50) -> List[Prediction]:
        """Retrieve recent prediction history for risk trajectory plotting."""
        from sqlalchemy import select, desc
        return list(self.db.execute(
            select(Prediction)
            .where(Prediction.patient_id == patient_id)
            .order_by(desc(Prediction.generated_at))
            .limit(limit)
        ).scalars().all())
