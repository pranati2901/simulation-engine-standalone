"""Aerospace domain plugin (Collins Aerospace POC vertical).

This is the reference plugin — copy this package structure for railway, hospital,
defence, ev, droneforce. It demonstrates every registration hook a plugin needs.
"""
from __future__ import annotations

from ...engine.catalog.spec import ActionSpec, register_action
from ...engine.enums import ActorCategory, Side
from ...engine.events import Emit
from ...engine.models.actors import ActorType, register_actor_type
from ...engine.models.resources import ResourceType, register_resource_type
from ...engine.workflows import RoleInfo, Workflow, WorkflowStep, register_role
from ..base import DomainPlugin


class AerospacePlugin(DomainPlugin):
    key = "aerospace"
    name = "Aerospace"

    def register(self) -> None:
        register_actor_type(ActorType(
            key="aircraft_hydraulic_system", name="Hydraulic System",
            category=ActorCategory.EQUIPMENT, domain=self.key, default_criticality=5,
        ))
        register_actor_type(ActorType(
            key="gate", name="Airport Gate",
            category=ActorCategory.FACILITY, domain=self.key, default_criticality=2,
        ))
        register_actor_type(ActorType(
            key="ground_crew", name="Ground Crew",
            category=ActorCategory.PERSONNEL, domain=self.key, default_criticality=2,
        ))
        # Cascade actors (downstream of the hydraulic leak):
        register_actor_type(ActorType(
            key="hydraulic_pump", name="Hydraulic Pump",
            category=ActorCategory.EQUIPMENT, domain=self.key, default_criticality=5,
        ))
        register_actor_type(ActorType(
            key="aircraft", name="Aircraft",
            category=ActorCategory.EQUIPMENT, domain=self.key, default_criticality=5,
        ))

        register_resource_type(ResourceType(
            key="redundant_hydraulic_line", name="Redundant Hydraulic Line", domain=self.key,
            default_scope="actor",
        ))
        register_resource_type(ResourceType(
            key="predictive_maintenance", name="Predictive Maintenance Alerting", domain=self.key,
            default_scope="global",
        ))

        register_action(ActionSpec(
            key="hydraulic_leak", name="Hydraulic Leak", category="fault", domain=self.key,
            requires_target=True,
            prevention={"redundant_hydraulic_line": 1},
            telemetry=[Emit(channel="ops", text="Hydraulic pressure dropping below threshold.")],
        ))
        register_action(ActionSpec(
            key="flight_delay", name="Flight Delay", category="downstream", domain=self.key,
            requires_target=False,
        ))
        register_action(ActionSpec(
            key="gate_congestion", name="Gate Congestion", category="downstream", domain=self.key,
            requires_target=True,
        ))
        # Cascade fault + consequence actions (see scenarios/definitions/aerospace/cascade.py):
        register_action(ActionSpec(
            key="pump_failure", name="Hydraulic Pump Failure", category="fault", domain=self.key,
            requires_target=True, prevention={"redundant_hydraulic_line": 1},
            telemetry=[Emit(channel="ops", text="Hydraulic pump load exceeding rated envelope.")],
        ))
        register_action(ActionSpec(
            key="emergency_landing", name="Precautionary Landing", category="fault", domain=self.key,
            requires_target=True,
            telemetry=[Emit(channel="ops", text="Crew requesting precautionary landing.")],
        ))
        for key, label in (
            ("runway_closure", "Runway Closure"),
            ("spares_shortage", "Spare-Parts Shortage"),
            ("maintenance_backlog", "Maintenance Backlog"),
            ("crew_overtime", "Crew Overtime / Duty-Time Breach"),
            ("financial_impact", "Financial Impact"),
        ):
            register_action(ActionSpec(key=key, name=label, category="downstream",
                                       domain=self.key, requires_target=False))

        register_action(ActionSpec(
            key="avionics_fault", name="Avionics Fault", category="fault", domain=self.key,
            requires_target=True,
        ))

        for role in self.roles():
            register_role(role)

    def roles(self) -> list[RoleInfo]:
        return [
            RoleInfo(role="maintenance", side=Side.RESPONSE, name="Maintenance Crew",
                     mission="Diagnose and repair the fault before it cascades.",
                     description="Runs inspection, repair and return-to-service tasks."),
            RoleInfo(role="ops_control", side=Side.OVERSIGHT, name="Operations Control",
                     mission="Manage schedule impact, gate reassignment, crew notifications.",
                     description="Reacts to severity/phase changes and coordinates recovery."),
        ]

    def default_workflows(self) -> dict[str, Workflow]:
        return {
            "maintenance": Workflow(
                role="maintenance", id="wf.maintenance.default", name="Default Maintenance Workflow",
                description="Baseline hydraulic fault response.",
                steps=[
                    WorkflowStep(id="insp01", role="maintenance", kind="inspect",
                                 label="Inspect hydraulic pressure telemetry", phase_hint="detect"),
                    WorkflowStep(id="rep01", role="maintenance", kind="repair",
                                 label="Isolate and repair leaking line", phase_hint="respond"),
                ],
            ),
        }
