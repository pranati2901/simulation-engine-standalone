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

# fault-specific response levers: each has a containment weight (w) and a cost (as a fraction
# of full exposure). Different faults have different levers with different effectiveness/cost,
# so the optimum genuinely differs per fault (e.g. remote-reboot dominates a charger fault;
# isolate-the-pack dominates a BESS thermal event).
LEVER_SETS = {
    "TX-1:overload": [
        {"id": "bess", "label": "Dispatch BESS", "w": 0.55, "cost": 0.05},
        {"id": "shed", "label": "Shed non-critical DC", "w": 0.40, "cost": 0.06},
        {"id": "curtail", "label": "Curtail charging", "w": 0.35, "cost": 0.08},
    ],
    "TX-1:overheat": [
        {"id": "cool", "label": "Force-cool transformer", "w": 0.50, "cost": 0.03},
        {"id": "throttle", "label": "Throttle DC power", "w": 0.40, "cost": 0.06},
        {"id": "shift", "label": "Shift load to Feeder F-2", "w": 0.30, "cost": 0.04},
    ],
    "F-1:overcurrent_trip": [
        {"id": "reclose", "label": "Re-close after load-shed", "w": 0.55, "cost": 0.04},
        {"id": "rebal", "label": "Rebalance to Feeder F-2", "w": 0.45, "cost": 0.06},
    ],
    "F-2:overcurrent_trip": [
        {"id": "shift", "label": "Shift AC bays to F-1", "w": 0.50, "cost": 0.05},
        {"id": "stagger", "label": "Stagger AC charging", "w": 0.35, "cost": 0.03},
    ],
    "DCFC:charger_offline": [
        {"id": "reboot", "label": "Remote-reboot OCPP", "w": 0.60, "cost": 0.01},
        {"id": "reroute", "label": "Reroute drivers", "w": 0.30, "cost": 0.03},
        {"id": "truck", "label": "Dispatch truck-roll", "w": 0.45, "cost": 0.09},
    ],
    "DCFC:connector_fault": [
        {"id": "lock", "label": "Lock + reroute", "w": 0.65, "cost": 0.02},
        {"id": "reset", "label": "Remote diagnostic reset", "w": 0.40, "cost": 0.03},
    ],
    "BESS-A:thermal_runaway": [
        {"id": "isolate", "label": "Isolate + cool pack", "w": 0.70, "cost": 0.03},
        {"id": "gridcov", "label": "Cover load from grid", "w": 0.30, "cost": 0.09},
    ],
    "BESS-A:offline": [
        {"id": "hold", "label": "Hold peak on grid", "w": 0.45, "cost": 0.07},
        {"id": "backup", "label": "Bring backup online", "w": 0.55, "cost": 0.05},
    ],
    "GRID:brownout": [
        {"id": "ride", "label": "Ride through on BESS + solar", "w": 0.60, "cost": 0.05},
        {"id": "curtail", "label": "Curtail DC-fast", "w": 0.35, "cost": 0.06},
    ],
    "GRID:supply_loss": [
        {"id": "island", "label": "Island on BESS + solar", "w": 0.55, "cost": 0.05},
        {"id": "priority", "label": "Prioritise AC bays", "w": 0.30, "cost": 0.02},
        {"id": "restart", "label": "Sequence restart", "w": 0.20, "cost": 0.03},
    ],
}
DEFAULT_LEVERS = [
    {"id": "bess", "label": "Dispatch BESS", "w": 0.50, "cost": 0.05},
    {"id": "shed", "label": "Shed non-critical load", "w": 0.35, "cost": 0.05},
    {"id": "curtail", "label": "Curtail charging", "w": 0.40, "cost": 0.06},
]
COND_PEN = {"peak": 0.15, "heatwave": 0.18, "rain": 0.08}


def _levers(asset: str, fault: str) -> list:
    return LEVER_SETS.get(f"{asset}:{fault}", DEFAULT_LEVERS)


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
    levers = _levers(req.assetId, req.faultId)
    steps = [0.0, 0.25, 0.5, 0.75, 1.0]

    def evaluate(vals):
        contain = min(0.95, sum(l["w"] * v for l, v in zip(levers, vals))) * (1 - cond)
        residual = full * (1 - prev * contain)
        action = full * sum(l["cost"] * v for l, v in zip(levers, vals))
        return residual, action, residual + action, contain

    best = None
    evals = 0
    for combo in itertools.product(steps, repeat=len(levers)):
        residual, action, tot, contain = evaluate(list(combo))
        evals += 1
        if best is None or tot < best["total"]:
            best = {"vals": list(combo), "contain": round(contain, 3),
                    "residual": round(residual), "action_cost": round(action), "total": round(tot)}

    # best achievable with a SINGLE lever (what a preset gives you) — to show the combo's edge
    best_single = None
    for i in range(len(levers)):
        for v in steps[1:]:
            vals = [0.0] * len(levers)
            vals[i] = v
            _, _, tot, _ = evaluate(vals)
            if best_single is None or tot < best_single:
                best_single = tot

    do_nothing = round(full)
    return {
        "full_exposure": do_nothing, "do_nothing": do_nothing,
        "optimal": {"contain": best["contain"], "residual": best["residual"],
                    "action_cost": best["action_cost"], "total": best["total"]},
        "savings": do_nothing - best["total"],
        "vs_single": round(best_single - best["total"]) if best_single is not None else 0,
        "evaluations": evals,
        "levers": [{"id": levers[i]["id"], "label": levers[i]["label"], "value": best["vals"][i]} for i in range(len(levers))],
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
