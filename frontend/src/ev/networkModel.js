// networkModel.js — the grounded model of the Gaadin energy site. Named assets (so "TX-1"
// resolves), their topology, the tariff/SLA cost basis, and which faults each asset can have.
// This is the "data layer" a real operator export would populate; here it's the demo network.

const DEFAULT_MODEL = {
  site: 'Gaadin Energy Site',
  currency: 'INR',
  cost: { rev_inr_per_kwh: 18, penalty_inr_per_hour_down: 1200, demand_charge_inr_per_kw: 350 },
  assets: [
    { id: 'TX-1',   name: 'Transformer T1',            type: 'transformer',  rating_kw: 630,  faults: ['overload', 'overheat'] },
    { id: 'F-1',    name: 'Feeder F-1 (DC-fast bank)', type: 'feeder',       capacity_kw: 400, chargers: 6, kw: 120, faults: ['overcurrent_trip'] },
    { id: 'F-2',    name: 'Feeder F-2 (AC bays + BESS)', type: 'feeder',     capacity_kw: 230, chargers: 8, kw: 22,  faults: ['overcurrent_trip'] },
    { id: 'DCFC',   name: 'DC-fast bank',              type: 'charger_bank', chargers: 6, kw: 120, faults: ['charger_offline', 'connector_fault'] },
    { id: 'BESS-A', name: 'BESS-A',                    type: 'bess',         capacity_kwh: 200, power_kw: 100, faults: ['thermal_runaway', 'offline'] },
    { id: 'GRID',   name: 'Grid supply (PCC)',         type: 'grid',         faults: ['brownout', 'supply_loss'] },
  ],
}

// MODEL is a live, swappable copy — the Data Layer can replace it with a company's real network.
export const MODEL = JSON.parse(JSON.stringify(DEFAULT_MODEL))
try { const saved = JSON.parse(localStorage.getItem('simcore_network') || 'null'); if (saved && saved.assets) Object.assign(MODEL, saved) } catch { /* ignore */ }

export function loadNetwork(net) {
  const clean = {
    site: net.site || MODEL.site,
    currency: net.currency || MODEL.currency,
    cost: { ...DEFAULT_MODEL.cost, ...(net.cost || {}) },
    assets: Array.isArray(net.assets) && net.assets.length ? net.assets : MODEL.assets,
  }
  Object.assign(MODEL, clean)
  localStorage.setItem('simcore_network', JSON.stringify(clean))
  return MODEL
}
export function resetNetwork() {
  Object.assign(MODEL, JSON.parse(JSON.stringify(DEFAULT_MODEL)))
  localStorage.removeItem('simcore_network')
  return MODEL
}
export const isDefaultNetwork = () => MODEL.site === DEFAULT_MODEL.site && MODEL.assets.length === DEFAULT_MODEL.assets.length
export const defaultNetwork = () => JSON.parse(JSON.stringify(DEFAULT_MODEL))

export const FAULTS = {
  overload:         { label: 'Overload trip at peak' },
  overheat:         { label: 'Overheating' },
  overcurrent_trip: { label: 'Overcurrent trip' },
  charger_offline:  { label: 'Chargers go offline' },
  connector_fault:  { label: 'Connector fault' },
  thermal_runaway:  { label: 'Thermal runaway risk' },
  offline:          { label: 'Goes offline' },
  brownout:         { label: 'Grid brownout' },
  supply_loss:      { label: 'Grid supply loss' },
}

export const assetById = (id) => MODEL.assets.find(a => a.id === id)
export const faultsFor = (id) => (assetById(id)?.faults || []).map(f => ({ id: f, label: FAULTS[f]?.label || f }))

// which real backend EV scenario the deterministic engine runs for Monte-Carlo grounding
export const engineScenarioFor = (assetId) =>
  assetById(assetId)?.type === 'charger_bank' ? 'ev.charger_fault_v1' : 'ev.grid_overload_v1'

// best-effort resolve of a free-text question → {assetId, faultId}
export function resolveText(q) {
  const t = (q || '').toLowerCase()
  let asset = MODEL.assets.find(a => t.includes(a.id.toLowerCase()) || t.includes(a.name.toLowerCase().split(' (')[0]))
  if (!asset) {
    if (/transformer|tx/.test(t)) asset = assetById('TX-1')
    else if (/bess|battery/.test(t)) asset = assetById('BESS-A')
    else if (/feeder/.test(t)) asset = assetById('F-1')
    else if (/grid|supply|brownout|outage/.test(t)) asset = assetById('GRID')
    else if (/charger|connector|dc.?fast|dcfc/.test(t)) asset = assetById('DCFC')
  }
  if (!asset) return null
  let faultId = asset.faults[0]
  if (/overheat|hot|temperature|thermal/.test(t) && asset.faults.includes('overheat')) faultId = 'overheat'
  if (/runaway|thermal/.test(t) && asset.faults.includes('thermal_runaway')) faultId = 'thermal_runaway'
  if (/connector/.test(t) && asset.faults.includes('connector_fault')) faultId = 'connector_fault'
  if (/offline|down|dead/.test(t) && asset.faults.includes('offline')) faultId = 'offline'
  if (/supply loss|blackout|outage|lose.*grid/.test(t) && asset.faults.includes('supply_loss')) faultId = 'supply_loss'
  if (/overload|trip/.test(t) && asset.faults.includes('overload')) faultId = 'overload'
  return { assetId: asset.id, faultId, matched: true }
}
