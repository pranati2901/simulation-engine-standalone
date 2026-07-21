// api.js — the ONLY place that talks to the engine. Swap this adapter and the same UI
// runs anywhere. Where the engine lives and how we authenticate is NOT decided here:
// config.js owns that, because it differs per deployment (dev proxy /engine, engine-served
// build at root, hub gateway /api/scenario). Hard-coding '/engine' here is what made the
// federated build call the HUB's origin and fail.
import { apiBase, authHeaders } from './config.js'

async function req(method, path, body) {
  const res = await fetch(apiBase() + path, {
    method,
    // credentials: the hub gateway authenticates by cookie, so the request must carry it.
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
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
  runGraph: (scenarioId, domain, readiness, environment, difficulty) => {
    try { localStorage.setItem('simcore_runs', String((+localStorage.getItem('simcore_runs') || 0) + 1)) } catch { /* ignore */ }
    return req('POST', '/runs/graph', { scenario_id: scenarioId, config: cfg(domain, readiness, difficulty), ...(environment !== undefined ? { environment } : {}) })
  },
  monteCarlo: (scenarioId, domain, iterations = 120) =>
    req('POST', '/runs/monte-carlo', { scenario_id: scenarioId, config: cfg(domain, 60), iterations }),
  author: (domain, prompt) => req('POST', '/scenarios/author', { domain, prompt }),
  ask: (context, question) => req('POST', '/analyst/ask', { context, question }),
  plan: (question, assets) => req('POST', '/analyst/plan', { question, assets }),
  evOptimize: (assetId, faultId, conditions = []) => req('POST', '/ev/optimize', { assetId, faultId, conditions }),
  evMultifault: (faults, conditions = []) => req('POST', '/ev/multifault', { faults, conditions }),
}
