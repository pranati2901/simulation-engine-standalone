"""Aerospace cascade graph — the downstream consequences the hydraulic leak can spawn.

This is the flagship Dynamic Scenario Graph. The root (hydraulic_leak_v1, defined in
hydraulic_leak.py) delays the flight, and that delay fans out:

    hydraulic_leak
      └─(always)──► flight_delay ─► gate_congestion ─┬─► maintenance_backlog ─┐
                                                      └─► crew_overtime        │
                                                                               ▼
                                                                     financial_impact

maintenance_backlog is a convergence point (gate congestion funnels into it), which makes
this a DAG rather than a tree: distinct knock-on effects funnel into the same loss.
"""
from __future__ import annotations

from ...factory import consequence_node, spawn, when
from ...loader import register_scenario

# --- any leak delays the flight -----------------------------------------------------

register_scenario(consequence_node(
    id="aerospace.flight_delay_cascade_v1", name="Flight Departure Delayed", domain="aerospace",
    action="flight_delay", category="operational", impact="medium",
    description="Repair time pushes the aircraft past its departure slot.",
    tags=["operational", "delay"],
    triggers=[when("always", spawn("aerospace.gate_congestion_cascade_v1", delay_min=15))],
))

register_scenario(consequence_node(
    id="aerospace.gate_congestion_cascade_v1", name="Gate Congestion", domain="aerospace",
    action="gate_congestion", target_type="gate", target_id="gate-cascade", target_name="Gate B12",
    category="operational", impact="medium",
    description="The delayed aircraft holds its gate; inbound aircraft stack up behind it.",
    tags=["operational"],
    triggers=[
        when("always", spawn("aerospace.maintenance_backlog_v1", delay_min=30)),
        when("always", spawn("aerospace.crew_overtime_v1", delay_min=10)),
    ],
))

register_scenario(consequence_node(
    id="aerospace.crew_overtime_v1", name="Crew Overtime / Duty-Time Breach", domain="aerospace",
    action="crew_overtime", category="human", impact="medium",
    description="Knock-on delays push the crew toward a duty-time limit.",
    tags=["human"],
))

# --- convergence points -------------------------------------------------------------

register_scenario(consequence_node(
    id="aerospace.maintenance_backlog_v1", name="Maintenance Backlog", domain="aerospace",
    action="maintenance_backlog", category="operational", impact="high",
    description="Deferred work from the event queues behind already-scheduled maintenance.",
    tags=["operational"],
    triggers=[when("always", spawn("aerospace.financial_impact_v1", delay_min=25))],
))

register_scenario(consequence_node(
    id="aerospace.financial_impact_v1", name="Financial Impact", domain="aerospace",
    action="financial_impact", category="financial", impact="critical",
    description="Delay compensation, lost utilisation and expedited spares.",
    tags=["financial"],
))
