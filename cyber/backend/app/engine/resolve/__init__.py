"""Deterministic resolution strategies: preconditions, success, detection, response.

These are the engine's swappable seams. The default implementations here are rule-based and
deterministic; a future AIResolver / RealSiemAdapter can replace them without touching run().
"""
