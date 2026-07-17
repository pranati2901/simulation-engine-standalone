# Scenario Engine ⇄ Hub integration — detailed, AWS-targeted

> Execution plan for integrating the **GoalCert Simulation (Scenario) Engine** into the Goalcert Hub. Phase 4 of the pivot (`PIVOT_PLAN.md`) — the last platform, after the Digital Twin (done) and Agentic AI (done). See `TWIN_INTEGRATION_PLAN.md` (NextXR repo) and `AGENTIC_INTEGRATION_PLAN.md` (AUTOMIND repo); this plan reuses their patterns and states only what differs.

## Context — the one greenfield integration

The hub ships a hand-ported Scenario UI (`hub/web/src/modules/simulation/**` ~2.9k lines + `modules/scenario/**`). Same drift problem as the others. But Scenario is different in one decisive way: **its frontend is being built right now**, so we do not retrofit — we build it to the federation contract from day one.

That is worth a lot. The two integrations before this each cost us a retrofit:
- **NextXR**: absolute asset paths 404'd on the hub's origin; providers composed across the boundary threw React #130; the sidebar and the remote's router desynced and trapped the user.
- **AUTOMIND**: built on React 19 → had to be downgraded to 18; a build-time-only API base plus two callers that bypassed the API client; Tailwind's preflight would have reset the hub's chrome; its own login wall had to be bypassed.

**None of that has to happen here.** Part 0 is the contract — build to it and the integration is mostly configuration.

---

## Part 0 — The contract the new frontend MUST meet

This is the most important section of this document. Hand it to whoever is building the Scenario UI.

### 0.1 Stack — non-negotiable
| Package | Version | Why |
|---|---|---|
| react / react-dom | **18.3.1** | Federation shares ONE React instance. The hub, NextXR and AUTOMIND are all 18.3. A 19-built remote crashes the moment it touches a 19-only API — AUTOMIND had to be downgraded for exactly this. |
| react-router-dom | **6.x** | matches the rest |
| vite | **5.4.x** | `@originjs/vite-plugin-federation` is not verified on Vite 6+ |
| @vitejs/plugin-react | **4.x** | pairs with Vite 5 |

### 0.2 Expose exactly ONE self-contained component
`./ScenarioRemoteApp` → `src/ScenarioRemoteApp.jsx`. It wraps **itself** in its own providers + `MemoryRouter` + routes, using its **own** module instances. The host renders that single component and nothing else.
> Do **not** expose providers/router separately for the host to compose — that is what caused React #130 (`invalid element type`) in the twin integration.

Props it must accept:
```jsx
<ScenarioRemoteApp
  initialPath="/"            // first mount only
  path="/runs"               // host nav → navigate here
  onNavigate={(p) => {}}     // internal nav → host highlights the right sidebar item
  activeDomain="edm-machine" // the hub's active twin domain (see 0.9)
/>
```

### 0.3 Shell/page separation
Chrome (sidebar/topbar) lives **only** in the standalone `App`, never inside a page component. The hub supplies the shell; a remote that renders its own sidebar shows a duplicate next to the hub's (AUTOMIND's `AppLayout` had to be dropped for this reason).

### 0.4 Router bridge (two-way)
Inside `MemoryRouter`, include a `RouterBridge` that: navigates when the `path` prop changes, and calls `onNavigate(location.pathname)` when the user navigates internally. Copy it verbatim from `TwinRemoteApp.jsx`.
> Without this, the hub's sidebar stays on the old item and clicking it does nothing — the user gets trapped. This was a real bug in the twin integration.

### 0.5 Runtime-configurable API base — ONE choke point
```js
export function apiBase() {
  if (typeof window !== 'undefined' && window.__SC_API_BASE__) return window.__SC_API_BASE__
  return import.meta.env.VITE_API_BASE || ''   // engine mounts at ROOT — no /api segment
}
```
The host sets `window.__SC_API_BASE__ = '/api/scenario'`. **Every** call — including any raw `fetch`/`EventSource` — must go through this. AUTOMIND had two callers that bypassed its client and hit the wrong origin.
> The engine mounts its routers at the **root** (`/scenarios`, `/runs`, `/catalog`…), so the base has no `/api` suffix: `${apiBase()}/scenarios` → `/api/scenario/scenarios` → gateway → `{ENGINE}/scenarios`.

### 0.6 No auth gate, no redirects
The hub owns identity — there is **no Scenario login**. If standalone needs the engine key, read it from `localStorage` and send `X-API-Key` (NextXR's pattern). Never `window.location = '/login'` on 401: it would blow away the hub SPA. Accept an injected header hook:
```js
window.__SC_AUTH__ = () => ({ 'X-CSRF-Token': '…' })  // set by the host
```

### 0.7 Assets + base
No absolute asset paths (`/logo.png`). Import through Vite (`import url from './x.svg?url'`). The build must honour `base: VITE_REMOTE_BASE` (an **absolute** origin) — otherwise assets resolve against the *hub's* origin and 404 (the twin's `turbine.glb` did exactly this).

### 0.8 CSS containment
Wrap everything in `<div className="sc-root">` and scope all globals to it. **No bare `body{}`, `html{}`, `*{}` or `::-webkit-scrollbar{}` rules** — the hub links this stylesheet into its own `<head>`, so unscoped rules restyle the hub's chrome. If you use Tailwind, set `corePlugins: { preflight: false }` for the remote build (the hub already ships `*{box-sizing:border-box;margin:0;padding:0}`).

### 0.9 Domain comes from the hub
Scenarios are **domain-scoped**, and in the hub the domain comes from the **active twin**. The host passes `activeDomain`; the UI must accept it rather than owning a domain picker as the sole source. Keep a picker as an override (the hub's current `BuilderPane` does this so all engine verticals stay runnable without a twin).
> The hub maps twin domain → sim domain via `TWIN_DOMAIN_TO_SIM` (`modules/simulation/engine/domains.js`) — that map moves into the new frontend.

### 0.10 Live updates: SSE, not WebSocket
The engine has a WS router (`app/ws/runs.py`), but **the hub gateway does not proxy WebSockets** — it forwards GET/POST/PUT/PATCH/DELETE and streams `text/event-stream` only. Use **SSE or polling** for run progress. Choosing WS means adding WS support to the gateway first.

### 0.11 Build config
```js
build: {
  target: 'esnext',        // required by module federation
  cssCodeSplit: false,     // one stylesheet the host can link deterministically
  rollupOptions: { output: { assetFileNames: (i) =>
    i.name?.endsWith('.css') ? 'assets/style.css' : 'assets/[name]-[hash][extname]' } },
}
```
The stable `assets/style.css` name is required — the hub derives the CSS href by string-replacing `remoteEntry.js` → `style.css`.

### 0.12 Do NOT re-implement the cascade engine
`hub/web/src/modules/simulation/engine/*` is a **client-side duplicate** of backend logic. The engine computes cascades **deterministically server-side** (`POST /runs/graph`). The new frontend renders results; it must not recompute them.

### 0.13 Page set (functional spec)
The hub's existing ported panes are the spec — port them **into the new app** as its canonical source:
| Page | Path | From (spec) | Key calls |
|---|---|---|---|
| Scenario Browser | `/` | `panes/BuilderPane` | `GET /catalog/*`, `GET /scenarios?domain=` |
| Builder / Author | `/author` | `components/AuthorScenario` | `POST /scenarios/author` (NL → runnable scenario) |
| Run / Cascade | `/run` | `panes/CascadePane` + `CascadeGraph`, `EventTimeline`, `Interventions`, `Safeguards`, `NodeInspector`, `Playbar` | `POST /runs/graph`, `GET /runs/graph/{id}` |
| History / Runs | `/runs` | `panes/HistoryPane` + `CompareModal` | `GET /runs`, `GET /runs/{id}` |
| Reports | `/reports` | `panes/ReportsPane` | `GET /dashboard`, run detail |

---

## Part 1 — Engine backend work

### 🔴 1.1 Pin the port (this bit us on AUTOMIND)
`start.bat` runs the engine on **:8000**; the hub's `.env` says `SCENARIO_BASE_URL=http://127.0.0.1:8002`. One of them is wrong — that mismatch is exactly what produced the `503` on `/api/agents/run` for AUTOMIND (hub pointed at 8001, service was on 8097). **Pick one and make `start.bat`, the README and the hub `.env` agree.**

### 1.2 Gateway prefix must stay EMPTY
The engine mounts at the root, so `SCENARIO_PATH_PREFIX=""`. `/api/scenario/scenarios` → `{BASE}/scenarios`. Already correct in `gateway.py` — do not "fix" it to `/api`.

### 1.3 Auth — nothing to build, but set the key
`verify_api_key` (`app/core/auth.py`) is a shared-secret `X-API-Key` check that the gateway injects server-side; `/health` is public; **unset key ⇒ allow-all (local dev)**. That is fine locally but means a deployed engine with no key is **completely open**. Set `SCENARIO_API_KEY` on the engine and the hub before any deploy.

### ⚠️ 1.4 No tenant model — a real multi-tenancy gap
The engine has **no user or org concept**: scenarios and runs are **global**. The hub is multi-tenant, so org A would see org B's authored scenarios and runs. The gateway already forwards `X-Goalcert-Org`/`X-Goalcert-User` — decide:
- **(a)** accept it for now (single-tenant demo), or
- **(b)** scope `Scenario`/`RunRecord` rows by `X-Goalcert-Org` (recommended before multi-tenant use).

This is the biggest open design question in this plan.

### 1.5 Serve the remote from the engine (mirror NextXR)
`app/main.py` already imports `StaticFiles`/`FileResponse` and serves `app/static/index.html` (the placeholder the README calls "not the real Hub UI"). Replace that with the built frontend's `dist/` mounted at `/` + `/assets`, exactly as NextXR does. Then **one process serves API + remote** — simpler than AUTOMIND, which needed a separate `vite preview` on :4174.
- Requires **CORS**: `cors_origins` defaults to an **empty list**, so the hub could not fetch `remoteEntry.js` cross-origin. Set `GOALCERT_CORS_ORIGINS` to the hub origin.
- Note `allow_credentials=True` + `"*"` is rejected by browsers — list the origin explicitly.

### 1.6 Persistence + deploy artifact (nothing exists yet)
- SQLite (`sqlite:///./simulation_engine.db`) ⇒ **authored scenarios are lost on redeploy**. Move to Postgres/RDS.
- There is **no Dockerfile, no compose, no render.yaml** in this repo — only `start.bat`. Create a Dockerfile that honours `$PORT` for ECS.

---

## Part 2 — Gateway (already done)

The `scenario` service already exists in `hub/backend/gateway.py` (`SCENARIO_BASE_URL` / `SCENARIO_API_KEY` / `SCENARIO_PATH_PREFIX=""` / module `scenario`). **No gateway change needed.** Verify with `GET /api/scenario/health` → 200 `X-Gateway-Source: live`.

---

## Part 3 — Hub host

1. **`ScenarioRemoteHost.jsx`** — copy `TwinRemoteHost.jsx` / `AgenticRemoteHost.jsx`; they already carry every lesson (lazy single-component mount, `useRemoteCss` link injection, error boundary → `RemoteSlot` fallback, router bridge). Set `window.__SC_API_BASE__ = '/api/scenario'`, `window.__SC_AUTH__ = () => authHeaders()`.
2. **Pass the domain**: derive `activeDomain` from hub `twinState.active` (via `TWIN_DOMAIN_TO_SIM`) and pass it in — see 0.9.
3. `vite.config.js` → add `scenarioEngine: env.VITE_SCENARIO_REMOTE` to `remotes`; add to `.env.local`.
4. **Nav/registry/personas** — replace the single `scenario` entry with the real page set (browser/author/run/history/reports) in `registry.jsx`, and update `personas.jsx` nav lists.
5. **Retire the ports**: delete `modules/simulation/**` and `modules/scenario/Scenario.jsx`; trim `API.scenario.*` from `api.js`.
6. **⚠️ `Trainer.jsx` (Train with AI)** — a guided-repair drill bound to the **active twin**, not really a Scenario page. Decide: fold into the twin remote or keep hub-native. (Still open from the twin plan.)

---

## Part 4 — AWS

Same shape as twin/agentic:
- **CloudFront**: `/remotes/scenario/<git-sha>/*` → **S3**, immutable + pointer-flip, OAC-locked, CI-only writes. *(If the engine serves its own dist per 1.5, that is the local story; on AWS still publish the remote to S3 so the hub's CSP and cache behaviour match the other remotes.)*
- **ECS Fargate, private VPC**: `scenario-api` reachable only via the hub gateway's internal ALB.
- **RDS Postgres** replaces SQLite.
- **Secrets Manager**: `SCENARIO_API_KEY`.
- **CSP**: add the scenario remote path to the hub's `script-src`.
- **CI**: frontend push → build → S3 `<sha>` → flip pointer → invalidate ⇒ hub picks it up with **zero hub deploy**. Backend push → ECR → ECS.

---

## Sequencing
- **S0** — Agree Part 0 with whoever is building the UI. **Do this before they go further** — the React 18/Vite 5 pin and the single-exposed-component shape are expensive to retrofit.
- **S1** — Engine: pin the port, set `SCENARIO_API_KEY`, set CORS, decide tenant scoping (1.4).
- **S2** — Frontend reaches feature parity with the ported panes (0.13) and builds a `remoteEntry.js` + `assets/style.css`.
- **S3** — Hub: `ScenarioRemoteHost`, remote config, nav/registry/personas, retire `modules/simulation`.
- **S4** — Engine deploy artifact: Dockerfile + `$PORT`, SQLite → Postgres.
- **S5** — AWS: private-VPC ECS, S3 remote, secrets, CSP, CI.

## Verification
- **Locally**: engine running (pinned port) + hub built and served by its backend on :8090 (federation host does **not** work under `vite dev`).
- Log in **once** → Scenario pages render natively → catalog/scenarios load via `/api/scenario/*` with `X-Gateway-Source: live` → **author a scenario from a sentence** → **run it** and see the cascade DAG → zero console errors.
- **Router bridge**: open a scenario from the browser page → the hub sidebar follows; click back → you can still switch scenarios (the trap the twin hit).
- **CSS containment**: the hub's own sidebar/topbar look **identical** before vs after the remote mounts.
- **Domain bridge**: open an EDM twin → Scenario defaults to that domain; the override picker still reaches the other verticals.
- **Degrade**: stop the engine → scenario pages show the slot fallback, the rest of the hub stays up.
- **Federation proof**: push a visible tweak to the scenario frontend → re-publish the remote → hub reflects it with **no hub rebuild**.
- **Security**: with `SCENARIO_API_KEY` set, a direct `curl {ENGINE}/scenarios` (no key) must **401**.

## Open decisions
- **Tenant scoping (1.4)** — accept global scenarios, or scope by `X-Goalcert-Org`? The only true blocker for multi-tenant use.
- **Where the remote is served** — engine-served (like NextXR, one process) vs separate static host (like AUTOMIND). Recommend engine-served locally, S3 on AWS.
- **`Trainer.jsx`** — twin remote or hub-native?
- **WS vs SSE** — if the UI wants WebSocket run streaming, the gateway needs WS proxying added (currently SSE only).
