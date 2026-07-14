"""Hospital domain plugin."""
from __future__ import annotations

from ...engine.catalog.spec import ActionSpec, register_action
from ...engine.enums import ActorCategory, Side
from ...engine.events import Emit
from ...engine.models.actors import ActorType, register_actor_type
from ...engine.models.resources import ResourceType, register_resource_type
from ...engine.workflows import RoleInfo, Workflow, WorkflowStep, register_role
from ..base import DomainPlugin


class HospitalPlugin(DomainPlugin):
    key = "hospital"
    name = "Hospital"

    def register(self) -> None:
        register_actor_type(ActorType(
            key="ward_hvac", name="Ward HVAC System", category=ActorCategory.EQUIPMENT,
            domain=self.key, default_criticality=4,
        ))
        register_actor_type(ActorType(
            key="operating_room", name="Operating Room", category=ActorCategory.FACILITY,
            domain=self.key, default_criticality=5,
        ))

        register_resource_type(ResourceType(
            key="backup_generator", name="Backup Generator", domain=self.key, default_scope="actor",
        ))
        register_resource_type(ResourceType(
            key="facilities_monitoring", name="Facilities Monitoring System",
            domain=self.key, default_scope="global",
        ))

        register_action(ActionSpec(
            key="hvac_failure", name="HVAC Failure", category="fault", domain=self.key,
            requires_target=True, prevention={"backup_generator": 1},
            telemetry=[Emit(channel="ops", text="Ward HVAC unit reporting temperature drift.")],
        ))
        register_action(ActionSpec(
            key="or_delay", name="Operating Room Delay", category="downstream", domain=self.key,
            requires_target=True,
        ))

        for role in self.roles():
            register_role(role)

    def roles(self) -> list[RoleInfo]:
        return [RoleInfo(
            role="facilities_engineer", side=Side.RESPONSE, name="Facilities Engineer",
            mission="Restore ward HVAC before it compromises operating room readiness.",
            description="Runs inspection, failover and restoration tasks.",
        )]

    def default_workflows(self) -> dict[str, Workflow]:
        return {
            "facilities_engineer": Workflow(
                role="facilities_engineer", id="wf.facilities_engineer.default",
                name="Default HVAC Fault Workflow",
                description="Baseline ward HVAC fault response.",
                steps=[
                    WorkflowStep(id="insp01", role="facilities_engineer", kind="inspect",
                                 label="Inspect HVAC telemetry", phase_hint="detect"),
                    WorkflowStep(id="rep01", role="facilities_engineer", kind="repair",
                                 label="Switch to backup generator, restore climate control",
                                 phase_hint="respond"),
                ],
            ),
        }
