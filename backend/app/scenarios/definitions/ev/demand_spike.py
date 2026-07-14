"""Scenario: mass simultaneous charging demand -> dynamic load balancing."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.demand_spike_v1",
    name="Demand Spike - Dynamic Load Balancing",
    domain="ev",
    description="All charger bays fill simultaneously during peak hours, pushing total "
                "site demand beyond contracted grid capacity. The energy manager must "
                "activate dynamic load balancing to distribute available power across "
                "all active sessions without tripping the main breaker.",
    node_kind="fault", category="operational", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="demand_threshold_breach", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="site_meter"),
                     label="Site demand exceeds contracted capacity threshold"),
        ScenarioStep(id="s2", action="dynamic_load_balancing", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="charging_network"),
                     label="Dynamic load balancing activated across all chargers"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Demand Spike Response",
                     correct_action="Activate dynamic load balancing, prioritise by SoC and session age, notify users of reduced rates.",
                     risk_level="high",
                     description="Financial and service risk: breaching contracted demand incurs penalty charges.",
                     consequence_of_delay="Main breaker trips or demand penalty charges accumulate.",
                     delay_s=300),
    ],
    objectives=[
        ScenarioObjective(text="Site demand brought within contracted capacity via load balancing",
                           role="energy_manager", condition="containment_rate == 1"),
        ScenarioObjective(text="No active sessions terminated involuntarily",
                           role="energy_manager", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="meter-1", type="site_meter", name="Site Main Meter"),
            ActorSpec(id="net-1", type="charging_network", name="Site Charging Network"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="smart_meter", targets=["meter-1"], scope="actor"),
            ResourceSpec(id="res-2", type="load_management_system"),
        ],
    ),
    tags=["demand", "load-balancing", "peak-hours"],
)

register_scenario(SCENARIO)
