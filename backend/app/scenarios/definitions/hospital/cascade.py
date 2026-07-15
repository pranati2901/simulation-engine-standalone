"""Hospital cascade graph — downstream of an unrestored ward HVAC failure.

A Dynamic Scenario Graph (a DAG, not a chain): the climate drift branches into distinct
clinical and logistical effects that then reconverge on a hospital-wide backlog.

    hvac_failure
      ├─(always)──────────► or_pressure_loss ──────► infection_risk ─────┐
      ├─(always)──────────► cold_chain_excursion ─┬► infection_risk       │ (converge)
      │                                           └► medication_spoilage  │
      └─(NOT contained)──► surgery_cancellation ───► patient_backlog ◄────┤
                                                     ▲                     │
      infection_risk / medication_spoilage ─────────┴─────────────────────┘ (converge)
"""
from __future__ import annotations

from ...factory import consequence_node, spawn, when
from ...loader import register_scenario

# --- first ring: immediate effects of the climate drift ------------------------------

register_scenario(consequence_node(
    id="hospital.or_pressure_loss_v1", name="Theatre Positive-Pressure Loss", domain="hospital",
    action="or_pressure_loss", target_type="operating_room", target_id="or-cascade",
    target_name="Operating Room 1", category="clinical", impact="high",
    description="With HVAC down, the theatre can no longer hold positive pressure against contaminants.",
    tags=["clinical"],
    triggers=[when("always", spawn("hospital.infection_risk_v1", delay_min=15))],
))

register_scenario(consequence_node(
    id="hospital.cold_chain_excursion_v1", name="Cold-Chain Temperature Excursion", domain="hospital",
    action="cold_chain_excursion", category="pharmacy", impact="high",
    description="Blood, vaccines and temperature-sensitive stock drift out of their safe range.",
    tags=["cold-chain"],
    triggers=[
        when("always", spawn("hospital.infection_risk_v1", delay_min=12)),
        when("always", spawn("hospital.medication_spoilage_v1", delay_min=10)),
    ],
))

register_scenario(consequence_node(
    id="hospital.surgery_cancellation_v1", name="Elective Surgery Cancellation", domain="hospital",
    action="surgery_cancellation", category="operational", impact="high",
    description="The theatre is stood down until climate control is restored, cancelling the list.",
    tags=["operational", "preventable"],
    triggers=[when("always", spawn("hospital.patient_backlog_v1", delay_min=15))],
))

# --- second ring: the effects reconverge --------------------------------------------

register_scenario(consequence_node(
    id="hospital.infection_risk_v1", name="Elevated Infection Risk", domain="hospital",
    action="infection_risk", category="clinical", impact="critical",
    description="Lost pressure and warm storage together raise the surgical-site infection risk.",
    tags=["clinical", "safety"],
    triggers=[when("always", spawn("hospital.patient_backlog_v1", delay_min=12))],
))

register_scenario(consequence_node(
    id="hospital.medication_spoilage_v1", name="Medication & Blood Spoilage", domain="hospital",
    action="medication_spoilage", category="pharmacy", impact="high",
    description="Spoiled stock must be quarantined and reordered, tightening supply during the incident.",
    tags=["pharmacy"],
    triggers=[when("always", spawn("hospital.patient_backlog_v1", delay_min=10))],
))

# --- convergence point --------------------------------------------------------------

register_scenario(consequence_node(
    id="hospital.patient_backlog_v1", name="Hospital-Wide Patient Backlog", domain="hospital",
    action="patient_backlog", category="operational", impact="critical",
    description="Cancelled lists, infection precautions and supply gaps back patients up across the hospital.",
    tags=["operational"],
))
