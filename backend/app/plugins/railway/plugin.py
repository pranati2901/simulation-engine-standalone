"""Railway domain plugin."""
from __future__ import annotations

from ...engine.catalog.spec import ActionSpec, register_action
from ...engine.enums import ActorCategory, Side
from ...engine.events import Emit
from ...engine.models.actors import ActorType, register_actor_type
from ...engine.models.resources import ResourceType, register_resource_type
from ...engine.workflows import RoleInfo, Workflow, WorkflowStep, register_role
from ..base import DomainPlugin


class RailwayPlugin(DomainPlugin):
    key = "railway"
    name = "Railway (SMRT-style)"

    def register(self) -> None:
        register_actor_type(ActorType(
            key="signal_block", name="Signal Block", category=ActorCategory.CONTROL_SYSTEM,
            domain=self.key, default_criticality=5,
        ))
        register_actor_type(ActorType(
            key="platform", name="Platform", category=ActorCategory.FACILITY,
            domain=self.key, default_criticality=3,
        ))
        register_actor_type(ActorType(
            key="train_unit", name="Train Unit", category=ActorCategory.EQUIPMENT,
            domain=self.key, default_criticality=4,
        ))

        register_resource_type(ResourceType(
            key="backup_signal_relay", name="Backup Signal Relay", domain=self.key, default_scope="actor",
        ))
        register_resource_type(ResourceType(
            key="cctv_monitoring", name="CCTV / Track Monitoring", domain=self.key, default_scope="global",
        ))

        register_action(ActionSpec(
            key="signal_failure", name="Signal Failure", category="fault", domain=self.key,
            requires_target=True, prevention={"backup_signal_relay": 1},
            telemetry=[Emit(channel="ops", text="Signal block reporting fail-safe state.")],
        ))
        register_action(ActionSpec(
            key="platform_overcrowding", name="Platform Overcrowding", category="downstream", domain=self.key,
            requires_target=True,
        ))
        # Cascade consequence actions (see scenarios/definitions/railway/cascade.py):
        for key, label in (
            ("passenger_medical_emergency", "Passenger Medical Emergency"),
            ("service_suspension", "Service Suspension"),
            ("line_wide_delay", "Line-Wide Delay"),
        ):
            register_action(ActionSpec(key=key, name=label, category="downstream",
                                       domain=self.key, requires_target=False))

        for role in self.roles():
            register_role(role)

    def roles(self) -> list[RoleInfo]:
        return [RoleInfo(
            role="signal_technician", side=Side.RESPONSE, name="Signal Technician",
            mission="Diagnose and restore signal block state before service impact compounds.",
            description="Runs inspection, relay-reset and service-restoration tasks.",
        )]

    def default_workflows(self) -> dict[str, Workflow]:
        return {
            "signal_technician": Workflow(
                role="signal_technician", id="wf.signal_technician.default",
                name="Default Signal Fault Workflow",
                description="Baseline signal block fault response.",
                steps=[
                    WorkflowStep(id="insp01", role="signal_technician", kind="inspect",
                                 label="Inspect signal block telemetry", phase_hint="detect"),
                    WorkflowStep(id="rep01", role="signal_technician", kind="repair",
                                 label="Reset relay and confirm fail-safe clear", phase_hint="respond"),
                ],
            ),
        }
