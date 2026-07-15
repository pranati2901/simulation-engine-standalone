"""Defence cascade graph — downstream of an unrestored comms relay failure.

A Dynamic Scenario Graph (a DAG, not a chain): several distinct effects branch from the
relay loss and then reconverge, so one root fault funnels into one critical outcome.

    comms_relay_failure
      ├─(always)──────────► coordination_breakdown ─────► delayed_qrf_response ─┐
      ├─(always)──────────► situational_awareness_loss ─┬► delayed_qrf_response │ (converge)
      │                                                 └► fires_deconfliction_risk
      └─(NOT contained)──► command_net_disruption ──────► mission_degradation ◄─┤
                                                          ▲                      │
      delayed_qrf_response / fires_deconfliction_risk ────┴──────────────────────┘ (converge)
"""
from __future__ import annotations

from ...factory import consequence_node, spawn, when
from ...loader import register_scenario

# --- first ring: the immediate effects of losing the relay ---------------------------

register_scenario(consequence_node(
    id="defence.coordination_breakdown_v1", name="Forward-Post Coordination Breakdown", domain="defence",
    action="coordination_breakdown", category="operational", impact="high",
    description="The forward post drops off the common operating picture and stops syncing movements.",
    tags=["coordination"],
    triggers=[when("always", spawn("defence.delayed_qrf_response_v1", delay_min=12))],
))

register_scenario(consequence_node(
    id="defence.situational_awareness_loss_v1", name="Situational Awareness Loss", domain="defence",
    action="situational_awareness_loss", category="operational", impact="high",
    description="Without the relay, sensor feeds and contact reports stop reaching the command post.",
    tags=["c2"],
    triggers=[
        when("always", spawn("defence.delayed_qrf_response_v1", delay_min=10)),
        when("always", spawn("defence.fires_deconfliction_risk_v1", delay_min=8)),
    ],
))

register_scenario(consequence_node(
    id="defence.command_net_disruption_v1", name="Command Net Disruption", domain="defence",
    action="command_net_disruption", category="c2", impact="high",
    description="The unrestored link severs the command net; orders must route the long way round.",
    tags=["c2", "preventable"],
    triggers=[when("always", spawn("defence.mission_degradation_v1", delay_min=15))],
))

# --- second ring: the effects reconverge --------------------------------------------

register_scenario(consequence_node(
    id="defence.delayed_qrf_response_v1", name="Delayed QRF Response", domain="defence",
    action="delayed_qrf_response", category="operational", impact="high",
    description="Coordination and awareness gaps push the quick-reaction force past its response window.",
    tags=["response"],
    triggers=[when("always", spawn("defence.mission_degradation_v1", delay_min=12))],
))

register_scenario(consequence_node(
    id="defence.fires_deconfliction_risk_v1", name="Fires Deconfliction Risk", domain="defence",
    action="fires_deconfliction_risk", category="safety", impact="critical",
    description="Degraded awareness raises the risk of a fires deconfliction error near friendly units.",
    tags=["safety"],
    triggers=[when("always", spawn("defence.mission_degradation_v1", delay_min=10))],
))

# --- convergence point --------------------------------------------------------------

register_scenario(consequence_node(
    id="defence.mission_degradation_v1", name="Mission Degradation", domain="defence",
    action="mission_degradation", category="operational", impact="critical",
    description="Slowed response, deconfliction risk and a broken command net degrade the mission.",
    tags=["mission"],
))
