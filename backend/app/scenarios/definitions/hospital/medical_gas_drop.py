"""Scenario: medical gas pressure drop -> operating room pressure loss.

A second launchable hospital fault, feeding the HVAC cascade's pressure-loss / surgery
branches so it reconverges on infection risk and the hospital-wide patient backlog.
"""
from __future__ import annotations

from ...factory import fault_node, spawn, when
from ...loader import register_scenario

register_scenario(fault_node(
    id="hospital.medical_gas_drop_v1", name="Medical Gas Pressure Drop - Theatre Risk", domain="hospital",
    action="medical_gas_drop", actor_type="operating_room", actor_id="or-gas", actor_name="Operating Room 2",
    gate_name="Medical Gas Fault Response",
    correct_action="Switch to the reserve manifold and isolate the leaking zone before theatre pressure falls.",
    description="Oxygen line pressure drops in the theatre block toward the alarm threshold.",
    risk="extreme", category="clinical", impact="critical",
    monitor_resource="facilities_monitoring",
    consequence_of_delay="The theatre loses safe gas supply and positive pressure.",
    tags=["medical-gas", "patient-safety"],
    triggers=[
        when("always", spawn("hospital.or_pressure_loss_v1", delay_min=15)),
        when("containment_rate < 1", spawn("hospital.surgery_cancellation_v1", delay_min=22)),
    ],
))
