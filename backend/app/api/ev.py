"""EV Decision Intelligence — a real optimiser over the response action-space, and multi-fault
composition. The optimiser searches lever combinations to minimise TOTAL cost (residual damage
+ cost of responding), so it finds the optimum rather than picking a preset."""
from __future__ import annotations

import itertools

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/ev", tags=["ev"])

HOURS = 6  # representative incident duration
COST = {"rev_inr_per_kwh": 18, "penalty_inr_per_hour_down": 1200}

# per (asset:fault): kW knocked offline, stations down, and the share a response can contain
SPEC = {
    "TX-1:overload": {"prev": 0.55, "kw": 480, "stations": 2},
    "TX-1:overheat": {"prev": 0.50, "kw": 260, "stations": 1},
    "F-1:overcurrent_trip": {"prev": 0.35, "kw": 420, "stations": 2},
    "F-2:overcurrent_trip": {"prev": 0.40, "kw": 150, "stations": 1},
    "DCFC:charger_offline": {"prev": 0.60, "kw": 240, "stations": 1},
    "DCFC:connector_fault": {"prev": 0.70, "kw": 120, "stations": 0},
    "BESS-A:thermal_runaway": {"prev": 0.50, "kw": 180, "stations": 1},
    "BESS-A:offline": {"prev": 0.60, "kw": 120, "stations": 0},
    "GRID:brownout": {"prev": 0.40, "kw": 360, "stations": 2},
    "GRID:supply_loss": {"prev": 0.30, "kw": 600, "stations": 3},
}
DEFAULT = {"prev": 0.5, "kw": 300, "stations": 1}

# response levers: containment weight + cost as a fraction of full exposure
LEVERS = [
    {"id": "bess", "label": "Dispatch BESS", "w": 0.50, "cost": 0.060},
    {"id": "shed", "label": "Shed non-critical load", "w": 0.35, "cost": 0.045},
    {"id": "curtail", "label": "Curtail charging", "w": 0.40, "cost": 0.055},
]
COND_PEN = {"peak": 0.15, "heatwave": 0.18, "rain": 0.08}


def _spec(asset: str, fault: str) -> dict:
    return SPEC.get(f"{asset}:{fault}", DEFAULT)


def _full(spec: dict) -> float:
    kwh = spec["kw"] * HOURS
    return kwh * COST["rev_inr_per_kwh"] + spec["stations"] * HOURS * COST["penalty_inr_per_hour_down"]


class OptimizeReq(BaseModel):
    assetId: str
    faultId: str
    conditions: list[str] = []


@router.post("/optimize")
def optimize(req: OptimizeReq):
    spec = _spec(req.assetId, req.faultId)
    full = _full(spec)
    prev = spec["prev"]
    cond = min(0.6, sum(COND_PEN.get(c, 0.0) for c in req.conditions))
    steps = [0.0, 0.25, 0.5, 0.75, 1.0]

    def evaluate(b, s, c):
        contain = min(0.92, LEVERS[0]["w"] * b + LEVERS[1]["w"] * s + LEVERS[2]["w"] * c) * (1 - cond)
        residual = full * (1 - prev * contain)
        action = full * (LEVERS[0]["cost"] * b + LEVERS[1]["cost"] * s + LEVERS[2]["cost"] * c)
        return residual, action, residual + action, contain

    best = None
    evals = 0
    for b, s, c in itertools.product(steps, steps, steps):
        residual, action, tot, contain = evaluate(b, s, c)
        evals += 1
        if best is None or tot < best["total"]:
            best = {"bess": b, "shed": s, "curtail": c, "contain": round(contain, 3),
                    "residual": round(residual), "action_cost": round(action), "total": round(tot)}

    do_nothing = round(full)
    curve = []
    for e in steps:
        residual, action, tot, _ = evaluate(e, e, e)
        curve.append({"effort": e, "exposure": round(residual)})
    return {
        "full_exposure": do_nothing, "do_nothing": do_nothing, "optimal": best,
        "savings": do_nothing - best["total"], "evaluations": evals,
        "levers": [{"id": l["id"], "label": l["label"], "value": best[l["id"]]} for l in LEVERS],
        "curve": curve,
    }


class MultiReq(BaseModel):
    faults: list[dict] = []
    conditions: list[str] = []


@router.post("/multifault")
def multifault(req: MultiReq):
    parts = []
    for fr in req.faults:
        spec = _spec(fr.get("assetId"), fr.get("faultId"))
        parts.append({"assetId": fr.get("assetId"), "faultId": fr.get("faultId"), "exposure": round(_full(spec))})
    base = sum(p["exposure"] for p in parts)
    n = len(parts)
    interaction = 0.15 * (n - 1) if n > 1 else 0.0   # concurrent faults on shared infra compound
    return {
        "parts": parts, "base_exposure": base, "count": n,
        "interaction_pct": round(interaction * 100),
        "combined_exposure": round(base * (1 + interaction)),
    }
