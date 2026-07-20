// api.js — the ONLY place that talks to the engine. Swap this adapter and the same UI
// runs anywhere (standalone here, or through the Hub gateway later). Requests go to
// /engine/* which Vite proxies to the FastAPI engine.
const BASE = '/engine'
const KEY = import.meta.env.VITE_API_KEY || ''

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-API-Key': KEY },
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
