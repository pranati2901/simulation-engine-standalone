"""Live-fire runner — execute real attacks for a completed precomputed simulation.

After the deterministic engine produces a RunResult, this module optionally
replays successful attack steps on a real lab and attaches actual results.
This bridges Tejesh's lab system (app/lab/) with the precomputed engine (app/engine/).

The model already ran — we know which techniques succeeded. Now we validate
on real infrastructure and produce a comparison report: model vs actual.

Usage:
    from app.engine.live_fire_runner import run_live_fire_validation
    result = run(scenario, env, config)  # normal precomputed sim
    validation = run_live_fire_validation(result, lab)  # optional real execution
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.lab.base import LabBackend
from app.lab.live_fire import FIRE_BY_ACTION, FireSpec, run_job

from .result import RunResult


# Map engine technique keys to live-fire action IDs
TECHNIQUE_TO_ACTION: dict[str, str] = {
    "recon": "recon.fingerprint",
    "discovery_ad": "intrecon.identity_graph",
    "exploit_public": "access.exposed_service",
    "phishing": "access.valid_creds",
    "lsass_dump": "cred.lsass",
    "kerberoast": "cred.kerberoast",
    "dcsync": "cred.dcsync",
    "lateral_wmi": "lateral.move",
    "lateral_psexec": "lateral.move",
}


@dataclass
class LiveFireResult:
    """Result of running live-fire validation on a completed simulation."""
    technique: str
    mitre_id: str
    target: str
    model_success: bool
    model_detected: bool
    model_detect_time_s: int
    # Real execution results (None if not executed)
    real_executed: bool = False
    real_success: bool | None = None
    real_detected: bool | None = None
    real_detect_evidence: str = ""
    real_duration_ms: int = 0
    real_output: str = ""
    tool: str = ""
    command: str = ""


@dataclass
class LiveFireValidation:
    """Full validation report comparing model predictions vs real results."""
    total_model_attacks: int = 0
    total_real_executed: int = 0
    total_real_success: int = 0
    total_real_detected: int = 0
    model_detection_rate: float = 0.0
    real_detection_rate: float = 0.0
    detection_delta: float = 0.0  # positive = model overestimates detection
    results: list[LiveFireResult] = field(default_factory=list)
    execution_time_ms: int = 0
    lab_backend: str = ""

    def summary(self) -> dict:
        return {
            "total_model_attacks": self.total_model_attacks,
            "total_real_executed": self.total_real_executed,
            "total_real_success": self.total_real_success,
            "total_real_detected": self.total_real_detected,
            "model_detection_rate": round(self.model_detection_rate * 100, 1),
            "real_detection_rate": round(self.real_detection_rate * 100, 1),
            "detection_delta_pct": round(self.detection_delta * 100, 1),
            "execution_time_ms": self.execution_time_ms,
            "lab_backend": self.lab_backend,
            "results": [_result_dict(r) for r in self.results],
        }


def _result_dict(r: LiveFireResult) -> dict:
    d = {
        "technique": r.technique, "mitre_id": r.mitre_id, "target": r.target,
        "model_success": r.model_success, "model_detected": r.model_detected,
        "model_detect_time_s": r.model_detect_time_s,
        "real_executed": r.real_executed,
    }
    if r.real_executed:
        d.update({
            "real_success": r.real_success, "real_detected": r.real_detected,
            "real_detect_evidence": r.real_detect_evidence,
            "real_duration_ms": r.real_duration_ms,
            "tool": r.tool, "command": r.command,
            "real_output": r.real_output[:500],
        })
    return d


def run_live_fire_validation(result: RunResult, lab: LabBackend) -> LiveFireValidation:
    """Replay successful attacks from a completed simulation on a real lab.

    BLOCKING — runs each attack sequentially. Call from a background thread.
    """
    start = time.time()
    lab_status = lab.status()

    validation = LiveFireValidation(lab_backend=lab_status.backend)

    # Extract attack events from the simulation result
    attack_events = [e for e in result.events if e.get("type") == "attack"]
    detection_events = {
        e.get("technique", ""): e
        for e in result.events if e.get("type") == "detection"
    }

    validation.total_model_attacks = len(attack_events)
    model_detected_count = 0

    for ev in attack_events:
        technique = ev.get("technique", "")
        mitre = ev.get("data", {}).get("mitre", technique)
        target_label = ev.get("asset_label", "unknown")
        success = ev.get("type") == "attack"  # attack events are successful by definition

        # Check if model detected this technique
        det_ev = detection_events.get(technique)
        model_detected = det_ev is not None
        model_detect_time = det_ev.get("t", 0) - ev.get("t", 0) if det_ev else 0
        if model_detected:
            model_detected_count += 1

        lfr = LiveFireResult(
            technique=technique, mitre_id=mitre, target=target_label,
            model_success=success, model_detected=model_detected,
            model_detect_time_s=model_detect_time,
        )

        # Try to execute on real lab
        action_id = TECHNIQUE_TO_ACTION.get(technique)
        if action_id and action_id in FIRE_BY_ACTION and lab_status.up:
            fire_result = run_job(lab, action_id)
            lfr.real_executed = True
            lfr.real_success = fire_result.get("success", False)
            lfr.real_detected = fire_result.get("detected", False)
            lfr.real_detect_evidence = fire_result.get("detection_evidence", "")
            lfr.real_duration_ms = fire_result.get("duration_ms", 0)
            lfr.real_output = fire_result.get("output", "")
            lfr.tool = fire_result.get("tool", "")
            lfr.command = fire_result.get("command", "")

            if lfr.real_success:
                validation.total_real_success += 1
            if lfr.real_detected:
                validation.total_real_detected += 1
            validation.total_real_executed += 1

        validation.results.append(lfr)

    # Compute rates
    if validation.total_model_attacks > 0:
        validation.model_detection_rate = model_detected_count / validation.total_model_attacks
    if validation.total_real_executed > 0:
        validation.real_detection_rate = validation.total_real_detected / validation.total_real_executed
    validation.detection_delta = validation.model_detection_rate - validation.real_detection_rate

    validation.execution_time_ms = int((time.time() - start) * 1000)
    return validation
