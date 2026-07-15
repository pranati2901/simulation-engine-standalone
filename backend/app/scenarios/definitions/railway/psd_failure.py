"""Scenario: platform screen door failure -> platform overcrowding.

A second launchable railway fault, feeding the signal-failure cascade's overcrowding /
suspension branches so it reconverges on the same line-wide delay outcome.
"""
from __future__ import annotations

from ...factory import fault_node, spawn, when
from ...loader import register_scenario

register_scenario(fault_node(
    id="railway.psd_failure_v1", name="Platform Screen Door Failure - Train Hold", domain="railway",
    action="psd_failure", actor_type="platform", actor_id="plat-psd", actor_name="Platform 4",
    gate_name="PSD Fault Response",
    correct_action="Isolate the faulty door pair and authorise degraded-mode berthing before dwell builds.",
    description="A platform screen door fails to release, holding the train and stalling boarding.",
    risk="high", category="equipment", impact="high",
    monitor_resource="cctv_monitoring",
    consequence_of_delay="Dwell time overruns and passengers stack on the platform.",
    tags=["psd", "service-disruption"],
    triggers=[
        when("always", spawn("railway.platform_overcrowding_cascade_v1", delay_min=12)),
        when("containment_rate < 1", spawn("railway.service_suspension_v1", delay_min=25)),
    ],
))
