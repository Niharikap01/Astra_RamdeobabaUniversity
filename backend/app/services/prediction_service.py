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
            trainer = LightGBMTrainer(artifacts_dir=settings.ml_artifacts_dir)
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

    def score_features(self, features_dict: Dict[str, float]) -> Tuple[float, str, List[Dict[str, Any]]]:
        """Compute calibrated probability, risk tier, and top clinical drivers."""
        assert self._feature_names is not None
        assert self._calibrator is not None

        x_row = np.array([[features_dict.get(k, 0.0) for k in self._feature_names]], dtype=float)
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
    ) -> Prediction:
        """Score patient feature vector and persist to predictions table."""
        prob, risk_level, top_factors = self.score_features(features_dict)

        pred_record = Prediction(
            patient_id=patient_id,
            probability=prob,
            risk_level=risk_level,
            model_version=self._model_version,
            generated_at=datetime.now(timezone.utc),
            top_factors=top_factors,
            feature_snapshot=features_dict,
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
