"""
SENTINEL — Centralized Settings

Loads and manages all project configuration from environment variables
and .env files using Pydantic Settings.
"""

from __future__ import annotations
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentinelSettings(BaseSettings):
    """
    Global settings for the SENTINEL system.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Redis ---
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str = Field(default="")

    # Redis hash the anomaly worker publishes its warm-up progress to, so the
    # dashboard can distinguish "still building baselines" from "no threats".
    anomaly_status_key: str = Field(default="sentinel:anomaly:status")

    # --- Threat Intelligence ---
    nvd_api_key: Optional[str] = Field(default=None)
    abuseipdb_api_key: Optional[str] = Field(default=None)
    otx_api_key: Optional[str] = Field(default=None)

    # --- Database ---
    db_url: str = Field(default="sqlite:///data/sentinel.db")

    # --- Capture Engine ---
    capture_interface: str = Field(default="wlan0")
    bpf_filter: str = Field(default="")

    # --- AI Engine ---
    ollama_base_url: str = Field(default="http://localhost:11434")
    llm_model: str = Field(default="gemma4:e2b")


# Global settings instance
settings = SentinelSettings()
