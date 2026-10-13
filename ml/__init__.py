"""NightWatch ML Package.

Feature engineering, time-series data preparation, LightGBM model training,
calibrated risk scoring, SHAP explainability, and evaluation.
"""

from .feature_engineering import FeatureEngineeringPipeline

__all__ = ["FeatureEngineeringPipeline"]
