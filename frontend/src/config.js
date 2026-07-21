// config.js — the ONE choke point for where the engine lives and how we authenticate.
//
// EVERY request must go through here — including any raw fetch/EventSource. A caller that
// bypasses this hits the wrong origin the moment it runs inside the hub.
//
// There are THREE deployments and they do NOT share a base:
//
//   1. `npm run dev` (:5200)  -> '/engine'
//      Vite proxies /engine/* to the engine on :8002 and strips the prefix, so the browser
//      sees one origin and the engine needs no CORS.
//
//   2. built, served BY the engine (:8002) -> '' (root)
//      Here the app and the API are the SAME origin, and the engine mounts its routers at
//      the ROOT (/scenarios, /runs, /catalog). There is no proxy and nothing strips
//      anything, so '/engine' would request :8002/engine/catalog/domains -> 404 and the
//      whole app would report "can't reach the engine" while the engine is running fine.
//      This is why the default is env-dependent rather than a constant.
//
//   3. federated into the Hub -> '/api/scenario' via window.__SC_API_BASE__
//      Routes through the hub's gateway. The base carries no /api segment of its own:
//      `${apiBase()}/scenarios` -> /api/scenario/scenarios -> gateway -> {ENGINE}/scenarios.
export function apiBase() {
  if (typeof window !== 'undefined' && window.__SC_API_BASE__) return window.__SC_API_BASE__
  if (import.meta.env.VITE_API_BASE != null) return import.meta.env.VITE_API_BASE
  return import.meta.env.DEV ? '/engine' : ''
}

// Auth headers. Standalone we send the engine's shared secret; the hub injects its own
// hook (CSRF token) because it terminates identity itself and adds X-API-Key server-side
// in the gateway — the browser never sees the engine key.
export function authHeaders() {
  if (typeof window !== 'undefined' && typeof window.__SC_AUTH__ === 'function') {
    try { return window.__SC_AUTH__() || {} } catch { return {} }
  }
  const key = (typeof localStorage !== 'undefined' && localStorage.getItem('simcore_api_key')) ||
    import.meta.env.VITE_API_KEY || ''
  return key ? { 'X-API-Key': key } : {}
}

// True when we're mounted inside the hub rather than running standalone. The shell uses
// this to drop its own chrome; pages use it to prefer the hub's twin over their picker.
export function isEmbedded() {
  return typeof window !== 'undefined' && !!window.__SC_API_BASE__
}
