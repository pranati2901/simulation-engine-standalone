"""Pydantic models for the Scenario Studio — the spec, the simulated run, KPIs, and training."""
from __future__ import annotations

from pydantic import BaseModel, Field

SEVERITIES = ("info", "low", "medium", "high", "critical")
OUTCOME_BANDS = ("Contained", "Degraded", "Severe", "Critical")


class ScenarioSpec(BaseModel):
    """A runnable what-if spec authored from natural language (any sector)."""
    name: str = Field(description="Short, specific scenario title.")
    domain: str = Field(default="generic", description="Sector/domain id, e.g. 'manufacturing'.")
    kind: str = Field(default="scenario", description="'scenario' (external situation) | 'fault' (component/system fault).")
    system: str = Field(default="", description="The asset/system under scenario, e.g. 'Assembly Line 3'.")
    fault: str = Field(default="none", description="A fault id from the domain catalogue, or 'none'.")
    severity: float = Field(default=0.7, ge=0.0, le=1.0, description="How aggressive/degraded (0..1).")
    intensity: float = Field(default=0.8, ge=0.0, le=1.0, description="Operating load/intensity during the run (0..1).")
    horizon_min: float = Field(default=60.0, ge=5.0, le=1440.0, description="Minutes to simulate forward.")
    description: str = Field(default="", description="The operator's situation description.")
    rationale: str = Field(default="", description="Why these parameters model the request.")
    expected_outcome: str = Field(default="", description="One-sentence prediction of the result.")
    objectives: list[str] = Field(default_factory=list, description="What a good response should achieve.")


class SimEvent(BaseModel):
    """One entry on the simulated timeline."""
    t_min: float = Field(description="Minutes from run start.")
    phase: str = Field(default="", description="Phase label, e.g. 'Onset', 'Detection', 'Impact'.")
    title: str = Field(description="Short event title.")
    detail: str = Field(default="", description="What happens.")
    severity: str = Field(default="info", description="info|low|medium|high|critical")
    actor: str = Field(default="system", description="Who/what: system | monitor | operator | agent.")


class RunMetrics(BaseModel):
    """Structured, objective outputs the simulation yields (drive the KPIs)."""
    time_to_detect_min: float | None = Field(default=None, description="When the situation is first detectable.")
    time_to_impact_min: float | None = Field(default=None, description="When material impact occurs, if any.")
    peak_severity: float = Field(default=0.5, ge=0.0, le=1.0, description="Worst instantaneous severity (0..1).")
    downtime_min: float = Field(default=0.0, description="Minutes of degraded/lost operation.")
    affected_units: int = Field(default=0, description="Assets/units impacted.")


class SimulationResult(BaseModel):
    """What the simulate-agent returns for a run (structured so KPIs stay objective)."""
    outcome_band: str = Field(description="Contained | Degraded | Severe | Critical.")
    headline: str = Field(description="One-line outcome summary.")
    timeline: list[SimEvent] = Field(description="Ordered events over the horizon.")
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    detections: list[str] = Field(default_factory=list, description="Signals/indicators that reveal it.")
    mitigations: list[str] = Field(default_factory=list, description="Actions that reduce impact.")
    risks: list[str] = Field(default_factory=list, description="Key risks if unaddressed.")


class Kpis(BaseModel):
    outcome_band: str = "Degraded"
    detected: bool = False
    mttd_min: float = 0.0            # mean/first time-to-detect
    lead_time_min: float = 0.0       # early-warning window (impact - detect)
    peak_severity_pct: int = 50
    downtime_min: float = 0.0
    affected_units: int = 0
    mitigations_identified: int = 0
    readiness_score: int = 0         # 0..100 objective score
    grade: str = "C"


class RunResult(BaseModel):
    id: str = ""
    scenario_id: str | None = None
    name: str = ""
    domain: str = "generic"
    system: str = ""
    status: str = "completed"
    duration_min: float = 60.0
    spec: ScenarioSpec | None = None
    outcome_band: str = "Degraded"
    headline: str = ""
    events: list[SimEvent] = Field(default_factory=list)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    detections: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    kpis: Kpis = Field(default_factory=Kpis)
    narrative: str = ""
    ai_mode: str = "stub"           # "agent" (Claude) | "stub" (deterministic)
    created_at: str = ""


# ── Training simulator (interactive guided repair) ─────────────────────

class TrainStep(BaseModel):
    id: str = Field(description="Short id like 'S1' in the CORRECT order.")
    title: str = Field(description="Short step name.")
    action: str = Field(description="Exactly what the operator/technician does.")
    rationale: str = Field(default="", description="Why this step matters.")
    criteria: str = Field(default="", description="How to confirm it was done correctly.")
    safety: bool = Field(default=False, description="True if a safety / isolation / lockout step.")
    requires: list[str] = Field(default_factory=list, description="Step ids that must precede this one.")
    skip_consequence: str = Field(default="", description="What goes wrong if skipped.")
    wrong_order_consequence: str = Field(default="", description="What goes wrong if done out of order.")


class Procedure(BaseModel):
    title: str
    fault: str = "none"
    domain: str = "generic"
    system: str = ""
    summary: str = ""
    steps: list[TrainStep] = Field(default_factory=list)
    success_criteria: str = ""
    common_mistakes: list[str] = Field(default_factory=list)


class TrainAction(BaseModel):
    step_id: str
    action: str = Field(description="'perform' | 'skip'")


class GradeLogEntry(BaseModel):
    step_id: str
    ok: bool
    severe: bool = False
    skipped: bool = False
    text: str = ""
    health_after: int = 0


class TrainingGrade(BaseModel):
    score: int = 100
    grade: str = "A"
    health_pct: int = 42
    performed: int = 0
    total: int = 0
    violations: int = 0
    skips: int = 0
    complete: bool = False
    log: list[GradeLogEntry] = Field(default_factory=list)
    summary: str = ""
