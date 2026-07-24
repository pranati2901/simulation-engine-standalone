"""Scenario Studio — a self-contained, LLM-driven what-if & training scenario engine.

Domain-agnostic: the operator describes a scenario for ANY sector in natural language; the agent
authors a runnable spec, the engine *simulates* it in-context (no external Digital Twin / physics),
scores the outcome against objective KPIs, and can turn any fault into an interactive training run.

The AI core lives here (Anthropic-backed, with deterministic stubs so everything runs before a key is
added). The Anthropic API key is set from the platform UI and stored via `settings_store`.
"""
