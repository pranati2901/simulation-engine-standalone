// api.js — the ONLY place that talks to the engine. Swap the base in config.js and the
// same UI runs anywhere: standalone against the Vite proxy, or through the Hub gateway.
//
// Nothing here may hardcode an origin, and no component may fetch() the engine directly.
import { apiBase, authHeaders } from './config.js'

async function req(method, path, body) {
  const res = await fetch(apiBase() + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    // Never redirect to a login on 401 — inside the hub that would blow away the whole
    // SPA. Surface it as an error and let the page render its own failed state.
    let detail = `${res.status}`
    try { detail = (await res.json()).detail || detail } catch { detail = (await res.text()) || detail }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

const cfg = (domain, readiness, difficulty = 'Hard') => ({ domain, readiness, difficulty, duration_min: 120 })

export const api = {
  health: () => req('GET', '/health'),
  domains: () => req('GET', '/catalog/domains'),
  scenarios: (domain) => req('GET', `/scenarios?domain=${encodeURIComponent(domain)}`),
  scenario: (id) => req('GET', `/scenarios/${encodeURIComponent(id)}`),

  runGraph: (scenarioId, domain, readiness, environment, difficulty) => {
    try { localStorage.setItem('simcore_runs', String((+localStorage.getItem('simcore_runs') || 0) + 1)) } catch { /* ignore */ }
    return req('POST', '/runs/graph', { scenario_id: scenarioId, config: cfg(domain, readiness, difficulty), ...(environment !== undefined ? { environment } : {}) })
  },
  monteCarlo: (scenarioId, domain, iterations = 120) =>
    req('POST', '/runs/monte-carlo', { scenario_id: scenarioId, config: cfg(domain, 60), iterations }),

  author: (domain, prompt) => req('POST', '/scenarios/author', { domain, prompt }),

  // Conversational scenario editing. `revise` PREVIEWS a change — it validates against the
  // live catalog but registers nothing, so the chat can propose and the operator decides.
  // `commit` registers the previewed scenario as a new variant; the seed is never mutated.
  revise: (id, instruction, scenario) =>
    req('POST', `/scenarios/${encodeURIComponent(id)}/revise`, { instruction, ...(scenario ? { scenario } : {}) }),
  commit: (scenario) => req('POST', '/scenarios/commit', { scenario }),

  ask: (context, question) => req('POST', '/analyst/ask', { context, question }),
}
