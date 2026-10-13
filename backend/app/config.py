"""Configuration management for NightWatch backend using pydantic-settings."""

from __future__ import annotations

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable override support."""

    app_name: str = "NightWatch"
    tagline: str = "A Sleep-Aware Digital Twin for Proactive Hypertension Risk Prediction"
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", env="APP_HOST")
    port: int = Field(default=8000, env="APP_PORT")

    # Database
    database_url: str = Field(
        default="sqlite:///./nightwatch.db",
        env="DATABASE_URL",
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,*",
        env="CORS_ORIGINS",
    )

    # Clinical Risk Bands
    risk_threshold_moderate: float = Field(default=0.35, env="RISK_THRESHOLD_MODERATE")
    risk_threshold_high: float = Field(default=0.65, env="RISK_THRESHOLD_HIGH")

    # Alert Cooldown
    alert_cooldown_hours: float = Field(default=24.0, env="ALERT_COOLDOWN_HOURS")

    # Simulation defaults
    simulation_patient_count: int = Field(default=200, env="SIMULATION_PATIENT_COUNT")
    simulation_history_days: int = Field(default=120, env="SIMULATION_HISTORY_DAYS")
    simulation_step_seconds: float = Field(default=10.0, env="SIMULATION_STEP_SECONDS")
    simulation_random_seed: int = Field(default=42, env="SIMULATION_RANDOM_SEED")

    # ML Artifacts
    ml_artifacts_dir: str = Field(default="ml/artifacts", env="ML_ARTIFACTS_DIR")
    model_version: str = Field(default="1.1.0", env="MODEL_VERSION")

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
