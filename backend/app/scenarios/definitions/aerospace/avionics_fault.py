"""Scenario: avionics dispatch fault -> flight delay cascade.

A second launchable aerospace fault. It reuses the flight-delay cascade already defined
in cascade.py, so an unresolved avionics fault feeds the same downstream graph the leak
does (delay -> gate congestion -> backlog / overtime -> financial impact).
"""
from __future__ import annotations

from ...factory import fault_node, spawn, when
from ...loader import register_scenario

register_scenario(fault_node(
    id="aerospace.avionics_fault_v1", name="Avionics Fault - Dispatch Hold", domain="aerospace",
    action="avionics_fault", actor_type="aircraft", actor_id="ac-av", actor_name="N54321",
    gate_name="Avionics Fault Response",
    correct_action="Run BITE diagnostics, clear the fault or apply MEL relief before the slot.",
    description="An avionics fault puts the aircraft in a no-dispatch state before its departure slot.",
    risk="high", category="equipment", impact="high",
    monitor_resource="predictive_maintenance",
    consequence_of_delay="The aircraft misses its departure slot.",
    tags=["avionics", "dispatch"],
    triggers=[when("always", spawn("aerospace.flight_delay_cascade_v1", delay_min=20))],
))
