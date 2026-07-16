"""Scenario: grid overload -> transformer load shedding. Second launchable EV fault."""
from __future__ import annotations

from ...factory import fault_node, spawn, when
from ...loader import register_scenario

register_scenario(fault_node(
    id="ev.grid_overload_v1", name="Grid Overload - Transformer Load Shedding", domain="ev",
    action="grid_overload", actor_type="transformer", actor_id="txf-b", actor_name="Transformer B",
    gate_name="Overload Response",
    correct_action="Shed non-critical load and cap charging rate before the transformer trips.",
    description="A demand spike pushes the substation transformer past its rated envelope.",
    risk="high", category="equipment", impact="high",
    monitor_resource="thermal_monitoring",
    consequence_of_delay="The transformer trips and drops the whole station.",
    tags=["ev", "grid"],
    triggers=[
        when("always", spawn("ev.transformer_overheat_v1", delay_min=10)),
        when("containment_rate < 1", spawn("ev.station_blackout_v1", delay_min=18)),
    ],
))
