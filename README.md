# Simulation Engine — NextXR Simulation Hub

Domain-agnostic scenario/simulation engine, extracted from GoalCert's architecture,
rebuilt around the GoalCert User Flow doc's single-operator competency-check pattern
(fault inject -> detect -> respond -> clearance). Destination: `Goalcert_Hub/simulation-engine/`.

Read `docs/ARCHITECTURE.md` first — it explains the v1 scope decision (why this isn't
a multi-role/multiplayer engine yet) and exactly what's real vs. deferred.

## What's real right now

- **4 working domains**: Aerospace (Collins Aerospace POC), Railway, Hospital, Defence
  — each with its own actor/resource/action/role definitions and a full scenario.
- A **real deterministic run loop**: fault injection, prevention checks, detection
  latency, decision-gate scoring against operator readiness, response, world-state
  mutation, KPI computation, objective evaluation, and a signed-style `ClearanceRecord`.
- A **frontend that shows every part of this**: switch domains, browse every scenario,
  preview a scenario's full timeline/decision gates/objectives/starting environment
  before running it, tune difficulty and readiness, run it, see a real
  CERTIFIED/NOT CERTIFIED banner, real KPIs, a real event timeline, and a Domain
  Catalog tab listing every registered actor type / resource type / action / role.

Every number changes when you change the readiness slider or difficulty dropdown —
nothing is hardcoded. See `docs/ARCHITECTURE.md`'s smoke-test output if you want proof
before you even run it yourself.

## Quickstart

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` — pick a domain, pick a scenario, adjust the sliders,
click Run Scenario.

## Layout

```
backend/app/
  engine/          Layers 1-6 — the domain-agnostic core (world, scenario, resolver, run loop)
  plugins/         Layer 10 — domain plugins: aerospace, railway, hospital, defence
  scenarios/       declarative scenario definitions + loader (1 scenario per domain)
  services/        run_manager, runner, twin_client, agent_client (stubs for the other 2 Hub services)
  api/             REST endpoints
  static/          the frontend (single-file HTML/JS, served at "/")
  ws/               live run streaming (stub — out of v1 scope)
  db/              persistence (stub — currently in-memory)
  reports/         Layer 9 — generic + plugin-extended reporting
  core/            settings
docs/
  ARCHITECTURE.md  full breakdown: v1 scope decision, what's real vs. deferred, Dynamic Scenario Graph
```

## Next real work (in priority order)

1. Persist runs/scenarios to a DB instead of in-memory dicts (`db/`).
2. Wire `services/twin_client.py` and `services/agent_client.py` once those repos exist.
3. If/when multi-role or cascading scenarios are actually needed, extend
   `engine/run.py` — the data model (`Scenario.triggers`, `Workflow`/`Posture`) is
   already reserved for it, see `docs/ARCHITECTURE.md`.
