"""Railway cascade graph — downstream of an unrestored signal block failure.

    signal_failure
      ├─(always)──────────► platform_overcrowding ─┬► passenger_medical ─► service_suspension ─┐
      │                                            └► escalator_congestion ─► line_wide_delay   │
      └─(NOT contained)──► service_suspension ◄──────────────────────────── (converge)          │
                                    └─► line_wide_delay ◄────────────────────────────────────────┘ (converge)
"""
from __future__ import annotations

from ...factory import consequence_node, spawn, when
from ...loader import register_scenario

register_scenario(consequence_node(
    id="railway.platform_overcrowding_cascade_v1", name="Platform Overcrowding", domain="railway",
    action="platform_overcrowding", target_type="platform", target_id="plat-cascade",
    target_name="Platform 2", category="operational", impact="medium",
    description="Held trains stack passengers on the platform as the signal stays down.",
    tags=["operational"],
    triggers=[
        when("always", spawn("railway.passenger_medical_v1", delay_min=15)),
        when("always", spawn("railway.escalator_congestion_v1", delay_min=8)),
    ],
))

register_scenario(consequence_node(
    id="railway.escalator_congestion_v1", name="Concourse & Escalator Congestion", domain="railway",
    action="escalator_congestion", category="operational", impact="medium",
    description="Overcrowding backs up onto the concourse and escalators, forcing crowd-control holds.",
    tags=["operational", "crowd"],
    triggers=[when("always", spawn("railway.line_wide_delay_v1", delay_min=18))],
))

register_scenario(consequence_node(
    id="railway.passenger_medical_v1", name="Passenger Medical Emergency", domain="railway",
    action="passenger_medical_emergency", category="human", impact="high",
    description="Crowding and heat trigger a passenger medical emergency needing evacuation.",
    tags=["human", "safety"],
    triggers=[when("always", spawn("railway.service_suspension_v1", delay_min=10))],
))

register_scenario(consequence_node(
    id="railway.service_suspension_v1", name="Service Suspension", domain="railway",
    action="service_suspension", category="operational", impact="high",
    description="The line is suspended to clear the incident and the failed signal.",
    tags=["operational"],
    triggers=[when("always", spawn("railway.line_wide_delay_v1", delay_min=20))],
))

register_scenario(consequence_node(
    id="railway.line_wide_delay_v1", name="Line-Wide Delay", domain="railway",
    action="line_wide_delay", category="operational", impact="critical",
    description="Suspension ripples across the network into peak-hour service-level breaches.",
    tags=["operational"],
))
