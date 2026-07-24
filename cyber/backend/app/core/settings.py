"""Application settings (env-overridable)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOALCERT_", env_file=".env", extra="ignore")

    # SQLite by default so the POC runs with zero infra. docker-compose sets a Postgres URL.
    database_url: str = "sqlite+pysqlite:///./goalcert.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Auth (signed-token, seeded demo account) ----------------------------
    auth_secret: str = "goalcert-dev-secret-change-me-in-prod"
    demo_email: str = "admin@goalcert.io"
    demo_password: str = "GoalCert@2026"
    # Default pacing: sim-seconds advanced per real second when streaming a run.
    default_stream_speed: float = 30.0
    seed_on_startup: bool = True

    # --- Live-fire range (real VMs + real tools) -----------------------------
    # All optional and OFF by default: the simulation runs unchanged unless a host arms live-fire
    # on a session AND the lab is up.
    lab_backend: str = "docker"          # "docker" (Phase 1) | "windows_ad" (Phase 2) — future: "proxmox"|"cloud"
    lab_compose_file: str = ""           # override; empty = infrastructure/docker-compose.lab.yml
    allow_lab_control: bool = True        # allow starting/stopping the lab via the API (local dev)
    lab_pool_max: int = 3                 # max concurrent per-session isolated ranges (Phase 3)

    # --- Windows Active Directory lab (Phase 2) ------------------------------
    # Defaults match infrastructure/Vagrantfile (DC01 on the host-only network).
    ad_dc_host: str = "192.168.56.10"
    ad_domain: str = "GOALCERT"           # NetBIOS domain used in DOMAIN/user
    ad_user: str = "vagrant"              # harvested attack credentials
    ad_password: str = "vagrant"
    ad_winrm_user: str = ""               # empty = reuse ad_user (for detection queries on the DC)
    ad_winrm_password: str = ""           # empty = reuse ad_password
    ad_vagrant_dir: str = ""              # empty = infrastructure/ (for vagrant up/halt)


settings = Settings()
