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

The engine runs on **port 8002**. That is not arbitrary: the hub's `SCENARIO_BASE_URL`
and the frontend's dev proxy both point at 8002, so all three must agree. (A port
mismatch of exactly this kind is what produced the 503s on the Agentic integration.)

```bash
# 1. the engine (API + the built frontend)
cd backend
python3 -m venv .venv
source .venv/bin/activate     # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

On Windows just run `start.bat` from the repo root — it does the same thing.

Open `http://127.0.0.1:8002/` — pick a scenario, tune it, run it.

```bash
# 2. the frontend, if you're working on it
cd frontend
npm install
npm run dev        # http://127.0.0.1:5200, proxies /engine/* -> :8002
npm run build      # -> frontend/dist, which the engine serves at /
```

The engine serves `frontend/dist` at `/` when it has been built, and falls back to the
old single-file placeholder in `app/static/` when it hasn't.

### Environment

Create `backend/.env` (same folder as `app/`). It is read by `app/core/settings.py`.

```ini
# Enables AI scenario AUTHORING and REVISION (the Builder's "Customise with AI").
# THIS IS THE ONE KEY TO SET. Without it those two endpoints return a clear 422 and
# everything else — library, cascade runs, simulation, reports, training — still works.
ANTHROPIC_API_KEY=sk-ant-...

# Model used for authoring/revision.
AUTHORING_MODEL=claude-opus-4-8

# Origins allowed to fetch the federated remote. Defaults to EMPTY, which blocks the hub.
# List the origin explicitly: "*" is rejected by browsers alongside credentialed requests.
GOALCERT_CORS_ORIGINS=["http://127.0.0.1:8090","http://localhost:8090"]

# Shared secret the hub's gateway injects as X-API-Key. UNSET MEANS ALLOW-ALL — fine
# locally, but a deployed engine with no key is completely open, and multi-tenancy then
# rests on nothing (see "Multi-tenancy" below). Must match SCENARIO_API_KEY in the hub's
# hub/backend/.env.
SCENARIO_API_KEY=

# Postgres for anything deployed — SQLite loses authored scenarios on redeploy.
# GOALCERT_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/scenario
```

The engine reads the key at startup, so restart it after editing `.env`. The **hub never
holds an LLM key for this** — the engine calls Claude itself; the model writes the scenario
*spec* and the engine still computes the cascade deterministically.

## Multi-tenancy

Scenarios and runs are scoped per tenant. The engine has no user model — the hub owns
identity and its gateway forwards `X-Goalcert-Org` from the authenticated session.

| Row | `org_id` | Who sees it |
|---|---|---|
| Seed scenario (`scenarios/definitions/**`) | `NULL` | **Every** tenant — the shared, tested library |
| Authored / revised scenario | the org | only that org |
| Run | the org | only that org (never shared) |

- Visibility rule lives in one place: `scenarios/loader.py::_visible`.
- No org header ⇒ no tenant context ⇒ sees only shared seeds. That is the safe direction,
  and it is why standalone works unchanged.
- A revision never mutates the original: it registers a **new** scenario owned by the
  reviser. Seeds are shared and other scenarios cascade into them by id, so an in-place
  edit would change every tenant's cascade at once.
- **This only holds if the engine is unreachable except through the gateway.** Anything
  that can reach it directly can set any org header it likes — which is what
  `SCENARIO_API_KEY` is for. Set it before any deploy.

## Hub integration

The frontend runs standalone **and** federates into the Goalcert Integration Hub. It
exposes exactly one component, `./ScenarioRemoteApp` (`src/ScenarioRemoteApp.jsx`), which
wraps itself in its own providers + `MemoryRouter`. The hub mounts that and nothing else.

- **API base**: everything goes through `src/config.js::apiBase()`. The hub sets
  `window.__SC_API_BASE__ = '/api/scenario'`; standalone it's the `/engine` dev proxy.
- **CSS**: every rule in `styles.css` is scoped under `.sc-root`. The hub links this
  stylesheet into its own `<head>`, so a bare `body{}`/`*{}` rule here would restyle the
  hub's chrome. The document reset lives in `index.html`, which never ships to the hub.
- **The domain comes from the hub**: scenarios are domain-scoped, and in the hub the
  domain comes from the active twin. See `src/domains.js`.

See `SCENARIO_INTEGRATION_PLAN.md` for the full contract.

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
