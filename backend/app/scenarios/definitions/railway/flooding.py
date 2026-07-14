"""Scenario: station flooding (ref: Braddell 2017) -> pump activation, evacuation."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.flooding_v1",
    name="Station Flooding - Pump Activation",
    domain="railway",
    description="Heavy rainfall overwhelms station drainage at concourse level "
                "(reference: Braddell MRT flooding, Oct 2017). The station manager must "
                "activate sump pumps, close affected entrances, and reroute passengers "
                "before water reaches platform track level.",
    node_kind="fault", category="environment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="flood_detection", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="station_concourse"),
                     label="Water level sensor triggers at concourse level"),
        ScenarioStep(id="s2", action="pump_activation", phase="diagnose", at_min=5.0,
                     target=TargetSelector(by="type", value="sump_pump"),
                     label="Sump pumps activated to drain concourse"),
        ScenarioStep(id="s3", action="entrance_closure", phase="respond", at_min=10.0,
                     target=TargetSelector(by="type", value="station_entrance"),
                     label="Affected station entrances closed to public"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Flood Response",
                     correct_action="Activate sump pumps, close low-lying entrances, alert OCC for service adjustment.",
                     risk_level="high",
                     description="Infrastructure-critical: water reaching track level shorts traction power.",
                     consequence_of_delay="Water ingress reaches platform and track level, forcing full station closure.",
                     delay_s=600),
    ],
    objectives=[
        ScenarioObjective(text="Sump pumps activated before water reaches platform level",
                           role="station_manager", condition="containment_rate == 1"),
        ScenarioObjective(text="Passengers safely rerouted away from flooded areas",
                           role="station_manager", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="conc-b", type="station_concourse", name="Concourse Level B"),
            ActorSpec(id="pump-1", type="sump_pump", name="Sump Pump 1"),
            ActorSpec(id="ent-a", type="station_entrance", name="Entrance A"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="water_level_sensor", targets=["conc-b"], scope="actor"),
            ResourceSpec(id="res-2", type="backup_pump", targets=["pump-1"], scope="actor"),
        ],
    ),
    tags=["flooding", "weather", "infrastructure"],
)

register_scenario(SCENARIO)
