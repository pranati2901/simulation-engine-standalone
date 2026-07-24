"""Per-scenario, tick-based topology simulation for the immersive cyber-range workspaces.

`topology` = the live host graph (VLANs, named hosts, per-host state machine).
`tools`    = the per-team, per-scenario tool catalogs (Red/Blue/SOC) + effects + workspace schemas.
`engine`   = `ScenarioSim`, the dynamic runtime that rides on a LiveSession: run_tool, worm
             propagation per tick, telegraphed auto-drivers, emergent outcome, saved AAR.
"""
