"""EV charging domain plugin."""
from __future__ import annotations

from ...engine.catalog.spec import ActionSpec, register_action
from ...engine.enums import ActorCategory, Side
from ...engine.events import Emit
from ...engine.models.actors import ActorType, register_actor_type
from ...engine.models.resources import ResourceType, register_resource_type
from ...engine.workflows import RoleInfo, Workflow, WorkflowStep, register_role
from ..base import DomainPlugin


class EVPlugin(DomainPlugin):
    key = "ev"
    name = "EV Charging"

    def register(self) -> None:
        register_actor_type(ActorType(
            key="dc_charger", name="DC Fast Charger", category=ActorCategory.EQUIPMENT,
            domain=self.key, default_criticality=4,
        ))
        register_actor_type(ActorType(
            key="transformer", name="Substation Transformer", category=ActorCategory.EQUIPMENT,
            domain=self.key, default_criticality=5,
        ))
        register_actor_type(ActorType(
            key="battery_pack", name="Buffer Battery Pack", category=ActorCategory.EQUIPMENT,
            domain=self.key, default_criticality=3,
        ))

        register_resource_type(ResourceType(
            key="backup_feed", name="Backup Grid Feed", domain=self.key, default_scope="actor",
        ))
        register_resource_type(ResourceType(
            key="thermal_monitoring", name="Thermal Monitoring", domain=self.key, default_scope="global",
        ))

        register_action(ActionSpec(
            key="charger_fault", name="DC Charger Fault", category="fault", domain=self.key,
            requires_target=True, prevention={"backup_feed": 1},
            telemetry=[Emit(channel="ops", text="DC fast-charger tripped offline mid-session.")],
        ))
        register_action(ActionSpec(
            key="grid_overload", name="Grid Overload", category="fault", domain=self.key,
            requires_target=True,
        ))

        # Cascade consequence actions (see scenarios/definitions/ev/cascade.py):
        for key, label in (
            ("charging_session_dropouts", "Charging Session Dropouts"),
            ("dc_load_imbalance", "DC Load Imbalance"),
            ("transformer_overheat", "Transformer Overheat"),
            ("thermal_runaway", "Battery Thermal Runaway"),
            ("station_blackout", "Station Blackout"),
            ("grid_strain", "Local Grid Strain"),
            ("revenue_loss", "Revenue & SLA Loss"),
        ):
            register_action(ActionSpec(key=key, name=label, category="downstream", domain=self.key))

        for role in self.roles():
            register_role(role)

    def roles(self) -> list[RoleInfo]:
        return [RoleInfo(
            role="grid_operator", side=Side.RESPONSE, name="Grid Operator",
            mission="Redistribute load and protect the transformer before the station cascades.",
            description="Runs load balancing, isolation and thermal-protection tasks.",
        )]

    def default_workflows(self) -> dict[str, Workflow]:
        return {
            "grid_operator": Workflow(
                role="grid_operator", id="wf.grid_operator.default",
                name="Default Charger Fault Workflow",
                description="Baseline DC charger fault response.",
                steps=[
                    WorkflowStep(id="insp01", role="grid_operator", kind="inspect",
                                 label="Read charger + transformer telemetry", phase_hint="detect"),
                    WorkflowStep(id="rep01", role="grid_operator", kind="repair",
                                 label="Redistribute load, isolate the faulted charger", phase_hint="respond"),
                ],
            ),
        }
