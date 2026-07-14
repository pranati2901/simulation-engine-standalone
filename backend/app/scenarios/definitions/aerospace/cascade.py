"""Aerospace cascade graph — the downstream consequences the hydraulic leak can spawn.

This is the flagship Dynamic Scenario Graph. The root (hydraulic_leak_v1, defined in
hydraulic_leak.py) branches two ways:

    hydraulic_leak
      ├─(always)──────────► flight_delay ─► gate_congestion ─┬─► maintenance_backlog ─┐
      │                                                       └─► crew_overtime        │
      └─(NOT contained)──► pump_failure ─┬─(NOT contained)─► emergency_landing         │
                                         │                     └─► runway_closure ──────┤
                                         └─(always)─► spares_shortage ─► maintenance_backlog
                                                                                        ▼
                                                                              financial_impact

The severe branch (pump failure → emergency landing → runway closure) only fires when
the operator FAILS to contain the fault — raise readiness past the gate threshold and it
never happens. Two convergence points (maintenance_backlog, financial_impact) make this a
DAG, not a tree: several distinct causes funnel into the same loss.
"""
from __future__ import annotations

from ...factory import consequence_node, fault_node, spawn, when
from ...loader import register_scenario

# --- severe branch: not contained → pump fails → emergency landing --------------------

register_scenario(fault_node(
    id="aerospace.pump_failure_v1", name="Hydraulic Pump Failure", domain="aerospace",
    action="pump_failure", actor_type="hydraulic_pump", actor_id="pump-1", actor_name="Pump PMP-1",
    gate_name="Pump Overload Response",
    correct_action="Shed hydraulic load and switch to the redundant pump before seizure.",
    description="The unresolved leak drives the main hydraulic pump past its rated envelope.",
    risk="high", category="equipment", impact="high",
    prevention_resource="redundant_hydraulic_line", monitor_resource="predictive_maintenance",
    consequence_of_delay="Pump seizes; aircraft is no longer dispatchable.",
    tags=["hydraulic", "equipment"],
    triggers=[
        when("containment_rate < 1", spawn("aerospace.emergency_landing_v1", delay_min=15)),
        when("always", spawn("aerospace.spares_shortage_v1", delay_min=40)),
    ],
))

register_scenario(fault_node(
    id="aerospace.emergency_landing_v1", name="Precautionary Emergency Landing", domain="aerospace",
    action="emergency_landing", actor_type="aircraft", actor_id="ac-emg", actor_name="N12345",
    gate_name="Divert / Landing Decision",
    correct_action="Declare, divert to the nearest suitable field, roll emergency services.",
    description="Loss of the pump forces a precautionary landing.",
    risk="extreme", category="safety", impact="critical",
    monitor_resource="predictive_maintenance",
    consequence_of_delay="Sustained flight on a failing hydraulic system.",
    tags=["safety", "divert"],
    triggers=[when("always", spawn("aerospace.runway_closure_v1", delay_min=5))],
))

register_scenario(consequence_node(
    id="aerospace.runway_closure_v1", name="Runway Occupied / Closure", domain="aerospace",
    action="runway_closure", category="operational", impact="high",
    description="The emergency landing occupies the active runway, closing it to other traffic.",
    tags=["operational"],
    triggers=[when("always", spawn("aerospace.financial_impact_v1", delay_min=30))],
))

register_scenario(consequence_node(
    id="aerospace.spares_shortage_v1", name="Spare-Parts Shortage", domain="aerospace",
    action="spares_shortage", category="supply", impact="high",
    description="Replacing the pump depletes on-hand spares; resupply lead-time bites.",
    tags=["supply"],
    triggers=[when("always", spawn("aerospace.maintenance_backlog_v1", delay_min=20))],
))

# --- inherent branch: any leak delays the flight ------------------------------------

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
    description="Delay compensation, diversion cost, lost utilisation and expedited spares.",
    tags=["financial"],
))
