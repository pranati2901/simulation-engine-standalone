import { defaultNetwork } from './networkModel.js'
// A Gaadin-style network of charging sites across a city. Exposure is a transparent estimate
// (kW at risk × tariff × incident hours + SLA) for triage; drilling into a site runs the full sim.

export const SITES = [
  { id: 'mall',     name: 'Mall Plaza',   area: 'City Centre', chargers: 12, transformer_kw: 630,  peak_util: 0.92, x: 34, y: 42 },
  { id: 'airport',  name: 'Airport Road', area: 'Aerocity',    chargers: 20, transformer_kw: 1000, peak_util: 0.86, x: 70, y: 28 },
  { id: 'techpark', name: 'Tech Park',    area: 'Whitefield',  chargers: 16, transformer_kw: 800,  peak_util: 0.71, x: 60, y: 64 },
  { id: 'highway',  name: 'Highway Hub',  area: 'NH-48',       chargers: 8,  transformer_kw: 500,  peak_util: 0.95, x: 20, y: 72 },
  { id: 'depot',    name: 'Metro Depot',  area: 'Depot Road',  chargers: 24, transformer_kw: 1200, peak_util: 0.64, x: 48, y: 18 },
]

const REV = 18, PEN = 1200, HRS = 6
export const siteExposure = (s) => Math.round(s.transformer_kw * s.peak_util * REV * HRS + s.chargers * s.peak_util * PEN * HRS)
export const siteRisk = (s) => (s.peak_util > 0.9 ? 'high' : s.peak_util > 0.75 ? 'med' : 'low')
export const siteToNetwork = (s) => ({ ...defaultNetwork(), site: `${s.name} · ${s.area}` })
