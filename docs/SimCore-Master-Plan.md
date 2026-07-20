# SimCore — Master Plan

> **Simulate Every Decision Before Reality.**
> An AI-powered Decision Operating System: ask any operational question in natural language,
> simulate multiple futures on real enterprise data, compare strategies, and watch cascading
> effects unfold in a live 3D digital twin — with explainable, evidence-backed answers.

First vertical: **EV charging networks** (Gaadin-style). Architecture is domain-agnostic
(airports, factories, ports, hospitals, railways, utilities, smart cities later).

---

## 1. The spine that makes it work (and kills hallucination)

The LLM appears **twice but never invents an outcome**:

```
NL question
  → ① LLM PLANNER      words → structured SimSpec  {targetAssets, intervention, params, horizon}
                        (validated against the ontology; unknown asset = honest "not in twin")
  → ② SIMULATION ENGINE the REAL result from the asset graph + physics/rules
                        (cascade, Monte Carlo, $ impact, ranked strategies) — the source of truth
  → ③ LLM EXPLAINER     narrates ONLY the engine's numbers (forbidden to add any)
  → ④ 3D TWIN           renders the engine's timeline frames (not the LLM's words)
```

**The engine is the source of truth. The LLM is the interface and the explainer.**

---

## 2. The six layers (and what already exists)

| Layer | What it is | Status |
|---|---|---|
| **1. Connectors** | SCADA / OCPP / EMS / BMS / weather / pricing / ERP / CMMS ingest | 🟡 sample data + requirements defined; live feeds new |
| **2. Semantic Ontology** | one asset graph — assets, relationships, dependencies, capacities, constraints, failure modes, costs. Everything references this, not raw sources | 🟡 `networkModel.js` seed; twin repo `nextxr-ontology/` to build on |
| **3. Simulation Engine** | cascade DAG + Monte Carlo + physics (power-flow, battery, queue) + discrete-event + agent-based + optimization | 🟢 cascade + Monte Carlo built; 🔴 physics/agent/optimization new |
| **4. AI Layer** | Planner (NL→SimSpec) + Explainer + Strategy generator | 🟢 Explainer (`/analyst`) working; 🔴 Planner + strategy-gen new |
| **5. 3D Digital Twin** | live animated world, click-to-inspect, camera fly-to, multi-future compare | 🟢 `evworld.js` built; 🟡 generalize + interactions |
| **6. UI Shell** | prompt-first home → Mission Control (assets L / 3D center / copilot R / timeline bottom) | 🔴 new build — Palantir × Vision Pro × Tesla FSD feel |

The two normally-hardest pieces — a working deterministic engine and a beautiful live twin — **already exist.** That's why this is realistic.

---

## 3. One question, end to end

*"What happens if Transformer T1 trips tomorrow at 5PM?"*

1. **Prompt homepage** (centered, ChatGPT-style) → Enter
2. **Reasoning timeline** streams — each line a *real* engine step (resolve asset → build cascade → run Monte Carlo → rank strategies → render), not a fake spinner
3. UI **morphs to Mission Control**
4. Twin **animates the full cascade** — transformer glows, feeder trips, all affected chargers/stations go red, BESS discharges, power reroutes, queues grow
5. **Strategy cards** (Do nothing / Activate BESS / Reroute / Dynamic pricing) — each a real engine re-run; click → 3D + numbers change
6. **Explainable answer** grounded in engine output, highlighting affected assets as it speaks

---

## 4. Build phases

### Phase 0 — the "wow" demo (weeks; runs on existing engine + twin)
- Prompt-first homepage + real reasoning timeline
- Planner endpoint (Claude → SimSpec) + **fenced** explainer (removes hallucination)
- **Full-cascade 3D animation** (all assets, not one wire)
- Cinematic timeline (clickable events → camera fly-to + rewind)
- **Strategy generator + side-by-side futures** — this replaces the confusing "readiness slider": *Do nothing vs Activate BESS* is the preventable story, made obvious
- Click-any-asset → grounded inspector

### Phase 1 — product foundation (months)
- Real ontology service (Postgres + graph) + live connectors (OCPP, weather, pricing)
- Physics modules: power-flow, battery, queue/agent
- Optimization for real strategy ranking; history-based fault priors

### Phase 2 — scale & verticals (quarters)
- Domain-agnostic ontology (swap the graph → airport/factory/port)
- Multi-tenant + auth + deploy (twin repo's *federation skeleton* is the start)
- Time Machine (infrastructure ageing / demand growth over years)

---

## 5. Honest reality check

- Full vision = multi-quarter, multi-engineer **product**.
- A demo that *feels* like 80% of it is close, because the hardest assets exist.
- The line between **demo-real** and **production-real** is **Layer 1 (connectors) + physics fidelity**. Every number will be explicitly on one side of that line.

---

## 6. Tech

- **Frontend:** React + Vite, Three.js (`evworld`), dark premium shell (Palantir/Vision-Pro/Tesla-FSD/Linear cues)
- **Engine:** FastAPI (existing standalone) — cascade DAG, Monte Carlo; add physics/agent/optimization modules
- **AI:** Claude (planner + explainer + strategy-gen), strictly fenced to engine output
- **Data:** ontology service + connectors (OCPP/SCADA/weather/pricing/ERP); CSV/API for pilots
