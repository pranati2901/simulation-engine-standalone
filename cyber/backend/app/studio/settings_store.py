"""Studio AI configuration — read from the environment (the operator sets the key on the server).

The Anthropic key comes from the ANTHROPIC_API_KEY environment variable (optionally the model from
ANTHROPIC_MODEL). Nothing is entered from the UI; `status()` is read-only so the frontend can show
whether Claude is wired up (agent) or running on deterministic stubs. The key is never exposed to the
browser — only a masked preview + a has_key flag.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-4-8"


@dataclass
class AiConfig:
    api_key: str = ""
    model: str = DEFAULT_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def get_config() -> AiConfig:
    return AiConfig(api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
                    model=os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL)


def status() -> dict:
    cfg = get_config()
    masked = ""
    if cfg.api_key:
        masked = f"{cfg.api_key[:7]}…{cfg.api_key[-4:]}" if len(cfg.api_key) > 14 else "set"
    return {"has_key": cfg.enabled, "source": "env" if cfg.enabled else "none",
            "model": cfg.model, "masked_key": masked,
            "ai_mode": "agent" if cfg.enabled else "stub"}
