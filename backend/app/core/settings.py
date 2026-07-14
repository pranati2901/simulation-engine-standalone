"""App settings. Loaded from environment variables (see .env.example once added)."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "GoalCert Simulation Engine"
    digital_twin_base_url: str = "http://localhost:8080"   # NextXR Digital Twin service
    agentic_ai_base_url: str = "http://localhost:8001"     # AUTOMIND Agentic AI service
    database_url: str = Field(
        default="sqlite:///./simulation_engine.db",
        validation_alias="GOALCERT_DATABASE_URL",
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias="GOALCERT_CORS_ORIGINS",
    )
    scenario_api_key: str = Field(default="", validation_alias="SCENARIO_API_KEY")

    class Config:
        env_file = ".env"


settings = Settings()