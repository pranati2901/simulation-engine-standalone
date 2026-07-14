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

    # ── LLM (scenario authoring, Jilla coaching, studio) ──
    # The engine calls Claude directly. It does NOT call an LLM to *simulate* anything —
    # the cascade stays deterministic. The model writes the scenario spec and the coaching
    # prose; engine/graph.py still computes what actually happens.
    #
    # (Both sides of the merge added anthropic_api_key independently, which left it
    # declared twice. Python takes the last one, so it worked — and would have quietly
    # confused whoever read it next. One declaration.)
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    authoring_model: str = Field(default="claude-opus-4-8", validation_alias="AUTHORING_MODEL")

    class Config:
        env_file = ".env"


settings = Settings()