"""Defence domain plugin."""
from __future__ import annotations

from ...engine.catalog.spec import ActionSpec, register_action
from ...engine.enums import ActorCategory, Side
from ...engine.events import Emit
from ...engine.models.actors import ActorType, register_actor_type
from ...engine.models.resources import ResourceType, register_resource_type
from ...engine.workflows import RoleInfo, Workflow, WorkflowStep, register_role
from ..base import DomainPlugin


class DefencePlugin(DomainPlugin):
    key = "defence"
    name = "Defence"

    def register(self) -> None:
        register_actor_type(ActorType(
            key="comms_relay", name="Comms Relay", category=ActorCategory.NETWORK,
            domain=self.key, default_criticality=5,
        ))
        register_actor_type(ActorType(
            key="forward_post", name="Forward Post", category=ActorCategory.FACILITY,
            domain=self.key, default_criticality=4,
        ))

        register_resource_type(ResourceType(
            key="backup_comms_link", name="Backup Comms Link", domain=self.key, default_scope="actor",
        ))
        register_resource_type(ResourceType(
            key="signal_monitoring", name="Signal Monitoring", domain=self.key, default_scope="global",
        ))

        register_action(ActionSpec(
            key="comms_relay_failure", name="Comms Relay Failure", category="fault", domain=self.key,
            requires_target=True, prevention={"backup_comms_link": 1},
            telemetry=[Emit(channel="ops", text="Comms relay reporting signal loss.")],
        ))
        register_action(ActionSpec(
            key="coordination_delay", name="Coordination Delay", category="downstream", domain=self.key,
            requires_target=True,
        ))

        for role in self.roles():
            register_role(role)

    def roles(self) -> list[RoleInfo]:
        return [RoleInfo(
            role="signals_operator", side=Side.RESPONSE, name="Signals Operator",
            mission="Restore comms relay before forward post coordination is compromised.",
            description="Runs diagnostics, failover-link activation and restoration tasks.",
        )]

    def default_workflows(self) -> dict[str, Workflow]:
        return {
            "signals_operator": Workflow(
                role="signals_operator", id="wf.signals_operator.default",
                name="Default Comms Fault Workflow",
                description="Baseline comms relay fault response.",
                steps=[
                    WorkflowStep(id="insp01", role="signals_operator", kind="inspect",
                                 label="Run relay diagnostics", phase_hint="detect"),
                    WorkflowStep(id="rep01", role="signals_operator", kind="repair",
                                 label="Activate backup comms link", phase_hint="respond"),
                ],
            ),
        }
