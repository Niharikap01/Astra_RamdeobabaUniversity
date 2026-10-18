"""Configuration management for NightWatch backend using pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Any
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve PROJECT_ROOT from this config file's location:
# backend/app/config.py -> parent is app, parent.parent is backend, parent.parent.parent is repository root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable override support."""

    project_root: Path = PROJECT_ROOT
    app_name: str = "NightWatch"
    tagline: str = "A Sleep-Aware Digital Twin for Proactive Hypertension Risk Prediction"
    environment: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT", "environment"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "log_level"))
    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("APP_HOST", "host"))
    port: int = Field(default=8000, validation_alias=AliasChoices("APP_PORT", "port"))

    # Database
    database_url: str = Field(
        default="sqlite:///./nightwatch.db",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    # Clinical Risk Bands
    risk_threshold_moderate: float = Field(default=0.35, validation_alias=AliasChoices("RISK_THRESHOLD_MODERATE", "risk_threshold_moderate"))
    risk_threshold_high: float = Field(default=0.65, validation_alias=AliasChoices("RISK_THRESHOLD_HIGH", "risk_threshold_high"))

    # Data Quality & Coverage Threshold
    min_coverage_threshold: float = Field(default=0.50, validation_alias=AliasChoices("MIN_COVERAGE_THRESHOLD", "min_coverage_threshold"))

    # Alert Cooldown
    alert_cooldown_hours: float = Field(default=24.0, validation_alias=AliasChoices("ALERT_COOLDOWN_HOURS", "alert_cooldown_hours"))

    # Simulation defaults
    simulation_patient_count: int = Field(default=200, validation_alias=AliasChoices("SIMULATION_PATIENT_COUNT", "simulation_patient_count"))
    simulation_history_days: int = Field(default=120, validation_alias=AliasChoices("SIMULATION_HISTORY_DAYS", "simulation_history_days"))
    simulation_step_seconds: float = Field(default=10.0, validation_alias=AliasChoices("SIMULATION_STEP_SECONDS", "simulation_step_seconds"))
    simulation_random_seed: int = Field(default=42, validation_alias=AliasChoices("SIMULATION_RANDOM_SEED", "simulation_random_seed"))

    # ML Artifacts, Data, and Documentation paths
    ml_artifacts_dir: str = Field(default="ml/artifacts", validation_alias=AliasChoices("ML_ARTIFACTS_DIR", "ml_artifacts_dir"))
    data_dir: str = Field(default="data", validation_alias=AliasChoices("DATA_DIR", "data_dir"))
    docs_dir: str = Field(default="docs", validation_alias=AliasChoices("DOCS_DIR", "docs_dir"))
    model_version: str = Field(default="1.1.0", validation_alias=AliasChoices("MODEL_VERSION", "model_version"))

    # Clinical Disclaimers
    clinical_disclaimer: str = (
        "NightWatch is a research prototype for clinical decision support. "
        "It does not diagnose hypertension, replace validated BP measurement, "
        "prescribe medication, or provide autonomous treatment recommendations. "
        "All data is synthetic or simulated."
    )
    whatif_disclaimer: str = (
        "Simulated scenario for clinical discussion. "
        "It does not guarantee that an intervention will produce the displayed outcome."
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def _validate_db_url(cls, v: str) -> str:
        """Resolve relative SQLite file paths against PROJECT_ROOT."""
        if v.startswith("sqlite:///") and not v.startswith("sqlite:///:memory:"):
            raw_path = v[len("sqlite:///"):]
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                path_obj = (PROJECT_ROOT / path_obj).resolve()
            return f"sqlite:///{path_obj.as_posix()}"
        return v

    @field_validator("ml_artifacts_dir", "data_dir", "docs_dir", mode="after")
    @classmethod
    def _validate_relative_paths(cls, v: str) -> str:
        """Resolve relative paths against PROJECT_ROOT."""
        path_obj = Path(v)
        if not path_obj.is_absolute():
            path_obj = (PROJECT_ROOT / path_obj).resolve()
        return str(path_obj)

    def model_post_init(self, __context: Any) -> None:
        """Load clinical decision thresholds from committed thresholds.json if present."""
        artifacts_path = Path(self.ml_artifacts_dir)
        thresholds_path = artifacts_path / "thresholds.json"
        if thresholds_path.exists():
            try:
                import json
                with open(thresholds_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "RISK_THRESHOLD_MODERATE" not in os.environ and "risk_threshold_moderate" not in os.environ:
                        self.risk_threshold_moderate = float(data.get("moderate", self.risk_threshold_moderate))
                    if "RISK_THRESHOLD_HIGH" not in os.environ and "risk_threshold_high" not in os.environ:
                        self.risk_threshold_high = float(data.get("high", self.risk_threshold_high))
            except Exception:
                pass

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins, disallowing wildcard when credentials are used."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip() and origin.strip() != "*"]
        return origins if origins else ["http://localhost:5173"]


settings = Settings()
