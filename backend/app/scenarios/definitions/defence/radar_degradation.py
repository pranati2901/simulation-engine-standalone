"""Scenario: radar picture degradation -> situational awareness loss.

A second launchable defence fault, feeding the comms cascade's SA-loss / command-net
branches so it reconverges on the same mission-degradation outcome.
"""
from __future__ import annotations

from ...factory import fault_node, spawn, when
from ...loader import register_scenario

register_scenario(fault_node(
    id="defence.radar_degradation_v1", name="Radar Picture Degradation - SA Loss", domain="defence",
    action="radar_degradation", actor_type="forward_post", actor_id="fp-radar", actor_name="Forward Post 5",
    gate_name="Radar Degradation Response",
    correct_action="Cross-cue alternate sensors and rebuild the track picture before command loses SA.",
    description="Radar returns degrade at the forward post, thinning the recognised air picture.",
    risk="high", category="c2", impact="high",
    monitor_resource="signal_monitoring",
    consequence_of_delay="Command loses situational awareness over the sector.",
    tags=["radar", "c2"],
    triggers=[
        when("always", spawn("defence.situational_awareness_loss_v1", delay_min=10)),
        when("containment_rate < 1", spawn("defence.command_net_disruption_v1", delay_min=18)),
    ],
))
