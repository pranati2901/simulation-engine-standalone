"""Live, human-driven multiplayer simulation layer (v3, additive to the precompute engine).

The v1/v2 engine *precomputes* a full deterministic timeline and replays it. This package adds a
parallel **live interactive** mode: multiple players join a session, pick a role, and a human
drives a team in real time against a shared, mutable World. Step 1 implements the **Red operator**
as a guided, mission-oriented lifecycle (see live/red_playbook.py) faithful to the Red Team
Masterclass — objective-first, minimum-footprint, detection-risk budgeted. Blue/SOC are reserved
seats (no defenders yet) and plug into the same session with no engine change.
"""
