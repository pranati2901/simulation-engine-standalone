"""The SOC operator's lifecycle as data — the triage/escalation layer between Red and Blue.

Mirror of `red_playbook.py` / `blue_playbook.py`, modelled on `soc-masterclass.md`: the alert
lifecycle (§6), triage methodology (§7), investigation (§8), escalation/incident declaration (§11)
and the one-page operator checklist (validate evidence, weight context, correlate, escalate on
uncertainty, scope before concluding). The SOC owns detection coverage + MTTA/MTTD and turns Red's
detected telemetry into *escalated incidents* that Blue (human or auto) then contains.

Two kinds of action: capability actions (turn on telemetry/correlation/intel — improve coverage)
and per-alert actions (triage / escalate a specific queued alert). Pure catalog + helpers.
"""
from __future__ import annotations


from dataclasses import dataclass

from app.engine.world import World


@dataclass(frozen=True)
class SocStage:
    id: str
    name: str
    summary: str
    ref: str


SOC_STAGES: list[SocStage] = [
    SocStage("monitor", "Visibility & Detection", "Turn on the telemetry, correlation and intel that surface adversary behaviour.", "§3.1–3.4 / §5"),
    SocStage("triage", "Triage", "Validate the evidence (not the label), weight context, decide real/urgent.", "§7"),
    SocStage("investigate", "Investigation", "Scope from evidence before concluding — find what you can't yet see.", "§8"),
    SocStage("escalate", "Escalation & Incident", "Declare the incident at the right severity and hand off to IR.", "§11"),
    SocStage("hunt", "Threat Hunting", "Assume breach — proactively find what didn't alert.", "§10"),
    SocStage("improve", "Continuous Improvement", "Tune the queue; turn every catch into a durable detection.", "§3.13 / §9"),
]
SOC_STAGE_INDEX = {s.id: i for i, s in enumerate(SOC_STAGES)}


@dataclass(frozen=True)
class SocAction:
    id: str
    stage: str
    label: str
    description: str
    ref: str = ""
    requires: tuple[str, ...] = ()
    target_mode: str = "none"            # none | alert
    alert_filter: str = ""               # new | triaged
    effects: tuple[str, ...] = ()        # see session._apply_soc_effects
    score: int = 10
    note: str = ""
    once: bool = True


def _s(*args, **kw) -> SocAction:
    return SocAction(*args, **kw)


SOC_ACTIONS: list[SocAction] = [
    # -- Visibility & detection -------------------------------------------- #
    _s("soc.collect", "monitor", "Verify telemetry sources are healthy",
       "Confirm log sources/sensors are feeding — a silently dead source is invisible until it's too late.",
       "§3.1", effects=("cap:collection",), score=8,
       note="Monitor the health of your monitoring — blind spots are where dwell time lives."),
    _s("soc.edr_monitoring", "monitor", "Onboard endpoint detection (EDR/Sysmon)",
       "Process lineage, LSASS access, persistence — the ground truth of what ran on a host.",
       "§5", effects=("monitor:endpoint",), score=10, note="Endpoint + identity cover the most paths."),
    _s("soc.identity_monitoring", "monitor", "Onboard identity/auth monitoring (UEBA/ITDR)",
       "Anomalous logon, ticket/token abuse, impossible travel — the modern perimeter.",
       "§5", effects=("monitor:identity",), score=12, note="Most intrusions touch identity."),
    _s("soc.network_monitoring", "monitor", "Onboard network + DNS detection (NDR)",
       "East-west movement, beaconing, exfiltration, newly-registered domains.", "§5",
       effects=("monitor:network",), score=10, note="DNS is cheap, powerful, hard to avoid."),
    _s("soc.correlation", "monitor", "Enable correlation rules",
       "Group related signals so 50 firings become one coherent case — catches multi-stage attacks.",
       "§6", effects=("cap:correlation",), score=10,
       note="Correlation turns 'two minor alerts' into a caught intrusion."),
    _s("soc.intel", "monitor", "Operationalise threat intel (TIP)",
       "Attach actor/IOC/TTP context to alerts for faster, higher-confidence triage.", "§12",
       effects=("cap:intel",), score=10, note="Intel is a targeting system, not a collection."),
    _s("soc.soar", "monitor", "Enable SOAR auto-enrichment",
       "Auto-attach asset/user/intel context before a human sees the alert — slashes MTTA.", "§16",
       effects=("cap:soar",), score=10, note="Automate the toil, elevate the human, gate the irreversible."),

    # -- Triage (per-alert) ------------------------------------------------ #
    _s("soc.triage", "triage", "Triage alert — validate & classify severity",
       "Validate the underlying evidence, weight asset/identity context, assign a P-level.",
       "§7", target_mode="alert", alert_filter="new", effects=("triage",), score=12, once=False,
       note="Validate the evidence, not the alert label. Never close a real alert to clear the queue."),

    # -- Investigation ----------------------------------------------------- #
    _s("soc.investigate", "investigate", "Investigate & scope the intrusion",
       "Pivot by entity (user→host→network) to find every affected asset before response.",
       "§8", requires=("compromised_exists",), effects=("cap:scoped",), score=16,
       note="Scope before you conclude — the visible activity is the tip, not the whole."),

    # -- Escalation -------------------------------------------------------- #
    _s("soc.escalate", "escalate", "Escalate alert — declare incident",
       "Hand the case to IR with context and the right severity; declares an incident on the asset.",
       "§11", target_mode="alert", alert_filter="triaged", effects=("escalate",), score=15, once=False,
       note="Escalate on uncertainty about severity, not certainty of badness."),

    # -- Threat hunting ---------------------------------------------------- #
    _s("soc.hunt", "hunt", "Threat hunt — persistence & living-off-the-land",
       "Assume breach: proactively search for footholds/persistence the alerts missed.", "§10",
       requires=("compromised_exists",), effects=("cap:hunted",), score=16,
       note="A hunt that finds nothing still finds a visibility gap."),

    # -- Continuous improvement -------------------------------------------- #
    _s("soc.tune", "improve", "Tune detections / reduce false positives",
       "Feed triage findings back to detection engineering so the queue gets quieter, not louder.",
       "§9", effects=("cap:tuned",), score=8, note="Every catch becomes a durable detection."),
]
SOC_ACTIONS_BY_ID: dict[str, SocAction] = {a.id: a for a in SOC_ACTIONS}


# --------------------------------------------------------------------------- #
#  Availability (capability/world predicates; alert-target availability is
#  resolved in the session, which owns the alert queue)
# --------------------------------------------------------------------------- #
def _req_ok(req: str, ss, world: World) -> bool:
    from app.engine.enums import SecurityState as _SS
    if req == "compromised_exists":
        return any(x.security_state == _SS.COMPROMISED for x in world.all_assets())
    if req.startswith("cap:"):
        return req.split(":", 1)[1] in ss.capabilities
    return True


def is_available(action: SocAction, ss, world: World) -> tuple[bool, str]:
    if action.once and action.id in ss.done_actions:
        return False, "already done"
    for req in action.requires:
        if not _req_ok(req, ss, world):
            return False, ("no compromised host yet" if req == "compromised_exists" else f"requires {req}")
    return True, ""
