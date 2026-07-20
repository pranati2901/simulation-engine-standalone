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
export const siteToNetwork = (s) => {
  const net = defaultNetwork()
  net.site = `${s.name} · ${s.area}`
  // tariff + ratings vary per site so switching sites changes the ₹ and capacities
  net.cost = { ...net.cost, rev_inr_per_kwh: Math.round(16 + s.peak_util * 6), demand_charge_inr_per_kw: Math.round(300 + s.transformer_kw * 0.08) }
  net.assets = net.assets.map(a =>
    a.type === 'transformer' ? { ...a, rating_kw: s.transformer_kw }
      : a.type === 'charger_bank' ? { ...a, chargers: Math.max(4, Math.round(s.chargers * 0.5)) }
        : a)
  return net
}
