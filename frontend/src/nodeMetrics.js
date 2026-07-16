import { moneyRate } from './assumptions.js'
// nodeMetrics.js — concrete, operational per-node metrics (trains held, flights delayed,
// charging sessions lost…) instead of an abstract "impact level". Editing the real numbers
// drives the node's $ contribution, which maps back to an impact tier the rest of the app
// already understands — so tangible input, consistent output.

// per-unit $ and a base quantity (at weight 1) chosen so Σ base×per == the domain's rate,
// keeping the tangible numbers reconciled with the existing exposure model.
const TPL = {
  railway:   [{ key: 'trains', label: 'Trains held', per: 15000, base: 12 }, { key: 'pax', label: 'Passenger-minutes delayed', per: 3, base: 40000 }],
  hospital:  [{ key: 'surgeries', label: 'Surgeries affected', per: 30000, base: 3 }, { key: 'patients', label: 'Patients affected', per: 600, base: 100 }],
  aerospace: [{ key: 'flights', label: 'Flights delayed', per: 50000, base: 5 }, { key: 'aog', label: 'Hours aircraft-on-ground', per: 30000, base: 5 }],
  defence:   [{ key: 'delay', label: 'Response delay (min)', per: 5000, base: 20 }, { key: 'readiness', label: 'Readiness drop (%)', per: 8000, base: 10 }],
  ev:        [{ key: 'sessions', label: 'Charging sessions lost', per: 800, base: 200 }, { key: 'mwh', label: 'MWh curtailed', per: 9000, base: 10 }],
}
const DEFAULT_TPL = [{ key: 'units', label: 'Impact units', per: 2000, base: 100 }]
const WEIGHT = { low: 0.4, medium: 1, high: 2.2, critical: 4 }

export function metricTemplate(domain) { return TPL[domain] || DEFAULT_TPL }

// seed concrete numbers from a node's current impact tier
export function seedMetrics(domain, impact) {
  const w = WEIGHT[impact] ?? 1
  const o = {}
  metricTemplate(domain).forEach(m => { o[m.key] = Math.round(m.base * w) })
  return o
}

export function metricsMoney(domain, metrics) {
  return metricTemplate(domain).reduce((a, m) => a + (Number(metrics?.[m.key]) || 0) * m.per, 0)
}

// map an edited $ back to the impact tier the exposure model consumes
export function tierFromMoney(domain, money) {
  const w = money / (moneyRate(domain) || 1)
  return w < 0.7 ? 'low' : w < 1.6 ? 'medium' : w < 3.1 ? 'high' : 'critical'
}
