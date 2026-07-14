"""Layer 5 — Roles & Workflows.

Each role's procedure is *data*: a list of tasks. Tasks are grouped by phase/stage and
each carries a **modeled effect** — so enabling/disabling a task mechanically changes
the simulation outcome, not just a checklist tick.

- `default_enabled` defines the workflow that runs out-of-the-box.
- `removable=False` marks a core task the operator cannot turn off.
- `effects` are aggregated into a deterministic Posture (see engine/posture.py) that
  modulates detection, prevention, response latency, containment and recovery.

The `kind` handle + `effects` are the action-space + guardrails a future AI-driven role
would consume — this is the hook for "AI agents can play any role" (Layer 8/AI-first).

Generic replacement for GoalCert's engine/workflows.py (red/blue/soc/mgmt/ot ->
domain-registered roles, still bucketed onto the 5 generic Side values).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Side


class TaskEffect(BaseModel):
    """A modeled effect a task contributes when enabled.

    kind — what it does (vocabulary lives in engine/posture.py, extendable per plugin).
    scope — optional category it applies to ("all" or an actor/action category).
    magnitude — strength (interpretation depends on kind; default 1).
    """
    kind: str
    scope: str | None = None
    magnitude: float = 1.0


class RoleInfo(BaseModel):
    role: str
    side: Side
    name: str
    mission: str
    description: str


class WorkflowStep(BaseModel):
    id: str
    role: str
    kind: str
    label: str
    description: str = ""
    phase_hint: str = ""
    source_ref: str = ""              # e.g. reference to the domain SOP/procedure this came from
    default_enabled: bool = True
    removable: bool = True
    effects: list[TaskEffect] = Field(default_factory=list)


class Workflow(BaseModel):
    role: str
    id: str
    name: str
    description: str
    steps: list[WorkflowStep] = Field(default_factory=list)


# Domain plugins register their own roles at startup (plugins/registry.py).
# This dict starts empty; the generic engine has no built-in domain roles.
ROLES: dict[str, RoleInfo] = {}


def register_role(info: RoleInfo) -> None:
    ROLES[info.role] = info


def get_workflow(role: str, workflows_by_role: dict[str, Workflow]) -> Workflow | None:
    return workflows_by_role.get(role)
