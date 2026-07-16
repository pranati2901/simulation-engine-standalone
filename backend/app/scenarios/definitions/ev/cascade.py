"""EV cascade graph — downstream of an unmanaged charger fault / grid overload.

A DAG that diverges and reconverges on revenue/SLA loss.

    charger_fault
      ├─(always)──► charging_session_dropouts ───────────────► revenue_loss
      ├─(always)──► dc_load_imbalance ─► transformer_overheat ─┬► grid_strain
      │                                                        └► revenue_loss
      └─(NOT contained)──► thermal_runaway ─► station_blackout ─► revenue_loss
"""
from __future__ import annotations

from ...factory import consequence_node, spawn, when
from ...loader import register_scenario

register_scenario(consequence_node(
    id="ev.charging_session_dropouts_v1", name="Charging Session Dropouts", domain="ev",
    action="charging_session_dropouts", category="operational", impact="medium",
    description="Active sessions drop as the faulted charger goes offline; drivers are stranded mid-charge.",
    tags=["operational"],
    triggers=[when("always", spawn("ev.revenue_loss_v1", delay_min=15))],
))

register_scenario(consequence_node(
    id="ev.dc_load_imbalance_v1", name="DC Load Imbalance", domain="ev",
    action="dc_load_imbalance", category="equipment", impact="high",
    description="Load shifts onto the remaining chargers, unbalancing the DC bus.",
    tags=["equipment"],
    triggers=[when("always", spawn("ev.transformer_overheat_v1", delay_min=12))],
))

register_scenario(consequence_node(
    id="ev.transformer_overheat_v1", name="Transformer Overheat", domain="ev",
    action="transformer_overheat", target_type="transformer", target_id="txf-cascade",
    target_name="Transformer A", category="equipment", impact="high",
    description="Concentrated load drives the substation transformer past its thermal limit.",
    tags=["equipment", "thermal"],
    triggers=[
        when("always", spawn("ev.grid_strain_v1", delay_min=10)),
        when("always", spawn("ev.revenue_loss_v1", delay_min=20)),
    ],
))

register_scenario(consequence_node(
    id="ev.thermal_runaway_v1", name="Battery Thermal Runaway", domain="ev",
    action="thermal_runaway", category="safety", impact="critical",
    description="The unmanaged fault tips a buffer battery pack into thermal runaway.",
    tags=["safety", "preventable"],
    triggers=[when("always", spawn("ev.station_blackout_v1", delay_min=8))],
))

register_scenario(consequence_node(
    id="ev.station_blackout_v1", name="Station Blackout", domain="ev",
    action="station_blackout", category="operational", impact="critical",
    description="Protection trips the site; the whole charging station goes dark.",
    tags=["operational"],
    triggers=[when("always", spawn("ev.revenue_loss_v1", delay_min=10))],
))

register_scenario(consequence_node(
    id="ev.grid_strain_v1", name="Local Grid Strain", domain="ev",
    action="grid_strain", category="operational", impact="medium",
    description="Load shedding ripples onto the local feeder, straining neighbouring demand.",
    tags=["operational"],
))

register_scenario(consequence_node(
    id="ev.revenue_loss_v1", name="Revenue & SLA Loss", domain="ev",
    action="revenue_loss", category="financial", impact="critical",
    description="Lost sessions, SLA penalties and reimbursement for stranded drivers.",
    tags=["financial"],
))
