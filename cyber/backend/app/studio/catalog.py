"""Domain-agnostic catalogue: sectors, external-situation presets, and fault catalogues.

Any sector works — the agent authors a runnable spec from free text against whichever domain is
chosen. These presets/faults are starting points (and ground the deterministic stub). A 'generic'
domain accepts anything.
"""
from __future__ import annotations

# id -> (label, icon, example system)
DOMAINS: dict[str, dict] = {
    "generic": {"label": "Generic / Any", "icon": "fa-diagram-project", "system": "System"},
    "manufacturing": {"label": "Manufacturing", "icon": "fa-industry", "system": "Assembly Line"},
    "energy": {"label": "Energy / Power", "icon": "fa-bolt", "system": "Power Plant"},
    "aviation": {"label": "Aviation / MRO", "icon": "fa-plane", "system": "Turbine Engine"},
    "rail": {"label": "Rail / Tram Network", "icon": "fa-train", "system": "Tram Network"},
    "datacenter": {"label": "Data Center", "icon": "fa-server", "system": "Data Hall"},
    "healthcare": {"label": "Healthcare / Hospital", "icon": "fa-hospital", "system": "Hospital Facility"},
    "edm-machine": {"label": "Wire EDM Machine", "icon": "fa-microchip", "system": "Wire-EDM Machine"},
    "maritime": {"label": "Maritime / Port", "icon": "fa-anchor", "system": "Container Terminal"},
    "logistics": {"label": "Logistics / Warehouse", "icon": "fa-boxes-stacked", "system": "Distribution Centre"},
    "utilities": {"label": "Water / Utilities", "icon": "fa-droplet", "system": "Treatment Plant"},
    "cybersecurity": {"label": "Cybersecurity / IT", "icon": "fa-shield-halved", "system": "Enterprise Network"},
}

FAULTS: dict[str, list[dict]] = {
    "manufacturing": [
        {"id": "spindle_bearing", "label": "CNC spindle bearing wear"},
        {"id": "robot_overload", "label": "Robot joint overload"},
        {"id": "conveyor_jam", "label": "Conveyor jam / overload"},
        {"id": "compressor_fault", "label": "Compressed-air failure"},
        {"id": "coolant_loss", "label": "Coolant / lubrication loss"},
    ],
    "energy": [
        {"id": "transformer_overheat", "label": "Transformer overheating"},
        {"id": "turbine_trip", "label": "Generator turbine trip"},
        {"id": "grid_frequency", "label": "Grid frequency excursion"},
        {"id": "breaker_failure", "label": "Circuit-breaker failure"},
    ],
    "aviation": [
        {"id": "blade_erosion", "label": "Blade erosion"},
        {"id": "nozzle_coking", "label": "Nozzle coking"},
        {"id": "bearing_wear", "label": "Bearing wear"},
        {"id": "oil_starvation", "label": "Oil starvation"},
        {"id": "compressor_fouling", "label": "Compressor fouling"},
        {"id": "surge", "label": "Compressor surge"},
    ],
    "rail": [
        {"id": "ohl_damage", "label": "Overhead line damage"},
        {"id": "substation_overload", "label": "Substation overload"},
        {"id": "track_buckling", "label": "Track buckling (heat)"},
        {"id": "switch_failure", "label": "Points / switch failure"},
        {"id": "signal_failure", "label": "Signalling failure"},
        {"id": "brake_degradation", "label": "Fleet brake degradation"},
    ],
    "datacenter": [
        {"id": "crac_failure", "label": "CRAC cooling failure"},
        {"id": "thermal_runaway", "label": "Rack thermal runaway"},
        {"id": "ups_depletion", "label": "UPS battery depletion"},
        {"id": "power_surge", "label": "Power distribution surge"},
    ],
    "healthcare": [
        {"id": "laminar_loss", "label": "OR laminar-flow loss"},
        {"id": "medgas_drop", "label": "Medical gas pressure drop"},
        {"id": "coldchain_excursion", "label": "Pharmacy cold-chain excursion"},
        {"id": "hvac_fault", "label": "Ward HVAC fault"},
    ],
    "edm-machine": [
        {"id": "wire_break", "label": "Wire breakage"},
        {"id": "dielectric_contamination", "label": "Dielectric contamination"},
        {"id": "flushing_loss", "label": "Flushing loss"},
        {"id": "chiller_failure", "label": "Dielectric chiller failure"},
        {"id": "servo_instability", "label": "Servo / gap-control instability"},
    ],
    "maritime": [
        {"id": "crane_hydraulics", "label": "Quay-crane hydraulic failure"},
        {"id": "reefer_powerloss", "label": "Reefer power loss"},
        {"id": "berth_congestion", "label": "Berth congestion"},
    ],
    "logistics": [
        {"id": "sorter_jam", "label": "Sorter / conveyor jam"},
        {"id": "agv_fault", "label": "AGV fleet fault"},
        {"id": "wms_outage", "label": "WMS system outage"},
    ],
    "utilities": [
        {"id": "pump_cavitation", "label": "Pump cavitation"},
        {"id": "chlorine_dosing", "label": "Chlorine dosing fault"},
        {"id": "membrane_fouling", "label": "Membrane fouling"},
    ],
    "cybersecurity": [
        {"id": "ransomware", "label": "Ransomware detonation"},
        {"id": "credential_theft", "label": "Credential theft / lateral movement"},
        {"id": "data_exfiltration", "label": "Data exfiltration"},
        {"id": "ddos", "label": "DDoS / availability attack"},
    ],
    "generic": [],
}

PRESETS: dict[str, list[dict]] = {
    "manufacturing": [
        {"title": "Three-shift rush order", "description": "Every line runs at maximum for three shifts to clear a rush order, stressing motors, spindles and robotics."},
        {"title": "Summer heat in the plant", "description": "High ambient temperature stresses motors, compressors and robotics across the shop floor."},
        {"title": "Skipped maintenance window", "description": "A planned lubrication/maintenance window is skipped under schedule pressure."},
        {"title": "Material hardness spike", "description": "A harder-than-spec material batch increases tool and spindle load."},
    ],
    "energy": [
        {"title": "Peak demand heatwave", "description": "A heatwave drives record demand while transformer cooling struggles."},
        {"title": "Unit trip during peak", "description": "A generating unit trips offline during the evening peak, stressing the remaining fleet."},
        {"title": "Grid islanding event", "description": "The plant is islanded from the grid and must hold frequency on local generation."},
    ],
    "aviation": [
        {"title": "Hot-and-high takeoff", "description": "Full-thrust ground run on a 45C day with reduced air density."},
        {"title": "Sustained max-continuous", "description": "Engine held at near-maximum thrust for an extended endurance run."},
        {"title": "Off-spec fuel batch", "description": "A batch of contaminated fuel feeds the combustor during a full-power run."},
    ],
    "rail": [
        {"title": "40 C heatwave afternoon", "description": "Extreme heat drives rail temperature toward the buckling limit while saloon HVAC load peaks the traction substations."},
        {"title": "Stadium event crowd surge", "description": "80,000 spectators leave the ground within 40 minutes — event-corridor loads spike and dwell times blow out."},
        {"title": "CBD signalling outage in the peak", "description": "An interlocking fault puts the core CBD junctions on manual working during the evening peak."},
        {"title": "Storm damage to the overhead", "description": "A storm brings a tree limb through the contact wire on one corridor; sections isolate and services divert."},
    ],
    "datacenter": [
        {"title": "AI training surge", "description": "Every rack pushed to 100% load for hours during a large model-training run."},
        {"title": "Cooling maintenance on a hot day", "description": "One CRAC unit is taken offline for service while ambient is high."},
        {"title": "Grid brownout", "description": "Utility power dips and the hall runs on UPS while the generator spins up."},
    ],
    "healthcare": [
        {"title": "Flu-season surge", "description": "Wards and ED at full occupancy for an extended period, stressing HVAC and med-gas."},
        {"title": "Heatwave on the OR HVAC", "description": "A heatwave stresses the operating-theatre air handling and laminar flow."},
        {"title": "Power failure", "description": "Mains fails and the hospital runs on emergency generator power."},
    ],
    "edm-machine": [
        {"title": "Summer heatwave", "description": "Shop ambient climbs toward 40C and the dielectric chiller struggles to hold tank temperature."},
        {"title": "Aggressive roughing run", "description": "Operator pushes maximum discharge energy for a fast roughing cut through thick stock."},
        {"title": "Unattended overnight cut", "description": "A long lights-out job runs for hours with nobody to clear debris or restore flushing."},
    ],
    "maritime": [
        {"title": "Peak vessel arrivals", "description": "Several large vessels arrive within one tide, stressing cranes, reefers and yard capacity."},
        {"title": "Heatwave on reefer stacks", "description": "A heatwave stresses reefer power and cooling across the yard."},
    ],
    "logistics": [
        {"title": "Peak-season parcel spike", "description": "Order volume triples over a promotional weekend, saturating sorters and AGVs."},
        {"title": "WMS upgrade weekend", "description": "A warehouse-management-system upgrade runs while volume stays high."},
    ],
    "utilities": [
        {"title": "Demand spike + heat", "description": "A heatwave spikes water demand while a treatment train is down for maintenance."},
        {"title": "Source water quality drop", "description": "Incoming raw-water quality degrades after upstream rain, stressing dosing and membranes."},
    ],
    "cybersecurity": [
        {"title": "Phishing to ransomware", "description": "A targeted phishing email leads to credential theft, lateral movement and enterprise-wide ransomware."},
        {"title": "EDR outage exploitation", "description": "An endpoint-protection outage is exploited for undetected lateral movement and exfiltration."},
    ],
    "generic": [
        {"title": "Peak-load stress test", "description": "The system is pushed to maximum sustained load for an extended period."},
        {"title": "Degraded-mode operation", "description": "A key component is offline and the system must run in a degraded/backup mode."},
    ],
}


def domains() -> list[dict]:
    return [{"id": k, **v, "fault_count": len(FAULTS.get(k, []))} for k, v in DOMAINS.items()]


def faults(domain: str) -> list[dict]:
    return FAULTS.get(domain, [])


def presets(domain: str) -> list[dict]:
    return PRESETS.get(domain, PRESETS["generic"])


def fault_label(domain: str, fault_id: str) -> str:
    for f in FAULTS.get(domain, []):
        if f["id"] == fault_id:
            return f["label"]
    return fault_id


# A few curated library scenarios seeded across sectors (feel the product before authoring).
SEED_SCENARIOS: list[dict] = [
    {"id": "seed-rail-heatwave", "name": "40 C Heatwave — Track Buckling Risk", "domain": "rail",
     "kind": "scenario", "is_seed": True,
     "description": "Extreme heat drives rail temperature toward the buckling limit while HVAC peaks the substations.",
     "spec": {"name": "40 C Heatwave — Track Buckling Risk", "domain": "rail", "kind": "scenario",
              "system": "Tram Network", "fault": "track_buckling", "severity": 0.85, "intensity": 0.9,
              "horizon_min": 180.0, "description": "Extreme heat drives rail temperature toward the buckling limit.",
              "expected_outcome": "Speed restrictions imposed on exposed corridors; service degraded but safe.",
              "objectives": ["Detect the rail-temperature trend early", "Impose speed restrictions before buckling",
                             "Protect the traction substations from thermal overload"]}},
    {"id": "seed-mfg-rush", "name": "Three-Shift Rush Order — Spindle Wear", "domain": "manufacturing",
     "kind": "fault", "is_seed": True,
     "description": "Sustained maximum load across three shifts accelerates CNC spindle bearing wear.",
     "spec": {"name": "Three-Shift Rush Order — Spindle Wear", "domain": "manufacturing", "kind": "fault",
              "system": "Assembly Line", "fault": "spindle_bearing", "severity": 0.8, "intensity": 0.95,
              "horizon_min": 480.0, "description": "Sustained maximum load accelerates spindle bearing wear.",
              "expected_outcome": "Vibration climbs; a bearing reaches its limit mid-shift without intervention.",
              "objectives": ["Trend vibration before the limit", "Schedule a bearing change proactively",
                             "Avoid an unplanned line stoppage"]}},
    {"id": "seed-dc-surge", "name": "AI Training Surge — Cooling Stress", "domain": "datacenter",
     "kind": "scenario", "is_seed": True,
     "description": "Every rack at 100% for hours during a large training run stresses CRAC cooling.",
     "spec": {"name": "AI Training Surge — Cooling Stress", "domain": "datacenter", "kind": "scenario",
              "system": "Data Hall", "fault": "thermal_runaway", "severity": 0.75, "intensity": 1.0,
              "horizon_min": 240.0, "description": "Every rack pushed to 100% load stresses hall cooling.",
              "expected_outcome": "Hot aisle climbs toward thermal limits; throttling needed to avoid trips.",
              "objectives": ["Detect the hot-aisle trend", "Rebalance load / add cooling before a trip",
                             "Keep critical racks within thermal limits"]}},
]
