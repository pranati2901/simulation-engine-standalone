// scenarios.js — the EV fault/cascade brain. For any (asset, fault) it produces a timeline of
// telemetry frames (which drive the 3-D twin) AND a structured facts object (which grounds the
// AI copilot). Every ₹ is a real formula (kWh × tariff, station-hours × SLA), never scripted.
import { MODEL, FAULTS } from './networkModel.js'

export const HEALTHY = {
  'ev:gridLoad': 66, 'ev:transformerTemp': 58, 'ev:loadHeadroom': 34, 'ev:peakDemand': 415,
  'ev:bessSoc': 72, 'ev:bessPower': 40, 'ev:solarOutput': 120, 'ev:sessionsActive': 6,
  'ev:faultedChargers': 0, 'ev:thermalRunawayRisk': 4, 'ev:cellTempMax': 31, 'ev:chargingPower': 180,
}

// peak = telemetry at worst; kwDown/stationsDown/faulted drive the $; preventable = share a
// prepared response can contain; onset/peak = envelope timing; rec = recommended action.
const SPEC = {
  'TX-1:overload':        { peak: { 'ev:gridLoad': 104, 'ev:transformerTemp': 88, 'ev:loadHeadroom': 1, 'ev:peakDemand': 690, 'ev:sessionsActive': 1, 'ev:chargingPower': 40, 'ev:bessSoc': 40, 'ev:bessPower': 95 }, kwDown: 480, stationsDown: 2, faulted: 6, preventable: 0.55, onset: 6, peak: 22, rec: 'Shed non-critical DC load and dispatch BESS to hold the transformer under 90%.' },
  'TX-1:overheat':        { peak: { 'ev:transformerTemp': 96, 'ev:gridLoad': 92, 'ev:loadHeadroom': 4, 'ev:chargingPower': 90, 'ev:bessPower': 70, 'ev:bessSoc': 45 }, kwDown: 260, stationsDown: 1, faulted: 3, preventable: 0.5, onset: 8, peak: 30, rec: 'Throttle DC-fast power and force-cool the transformer before it derates.' },
  'F-1:overcurrent_trip': { peak: { 'ev:gridLoad': 50, 'ev:sessionsActive': 1, 'ev:chargingPower': 30, 'ev:peakDemand': 300 }, kwDown: 420, stationsDown: 2, faulted: 6, preventable: 0.35, onset: 4, peak: 16, rec: 'Re-close the feeder after load-shed; rebalance the DC bank onto F-2 headroom.' },
  'F-2:overcurrent_trip': { peak: { 'ev:gridLoad': 58, 'ev:sessionsActive': 3, 'ev:chargingPower': 120 }, kwDown: 150, stationsDown: 1, faulted: 4, preventable: 0.4, onset: 4, peak: 16, rec: 'Shift AC bays onto F-1 headroom and re-close.' },
  'DCFC:charger_offline': { peak: { 'ev:sessionsActive': 3, 'ev:chargingPower': 120 }, kwDown: 240, stationsDown: 1, faulted: 3, preventable: 0.6, onset: 4, peak: 14, rec: 'Remote-reboot the OCPP session controller; truck-roll only if it fails.' },
  'DCFC:connector_fault': { peak: { 'ev:sessionsActive': 5, 'ev:chargingPower': 150 }, kwDown: 120, stationsDown: 0, faulted: 1, preventable: 0.7, onset: 3, peak: 10, rec: 'Lock the faulted connector and route drivers to the adjacent bay.' },
  'BESS-A:thermal_runaway': { peak: { 'ev:thermalRunawayRisk': 64, 'ev:cellTempMax': 49, 'ev:bessSoc': 20, 'ev:bessPower': 0, 'ev:gridLoad': 94, 'ev:loadHeadroom': 5 }, kwDown: 180, stationsDown: 1, faulted: 1, preventable: 0.5, onset: 6, peak: 24, rec: 'Isolate BESS-A, trigger cooling, and cover load from grid within the demand-charge cap.' },
  'BESS-A:offline':       { peak: { 'ev:bessSoc': 10, 'ev:bessPower': 0, 'ev:gridLoad': 90, 'ev:loadHeadroom': 8 }, kwDown: 120, stationsDown: 0, faulted: 0, preventable: 0.6, onset: 4, peak: 16, rec: 'Hold peak on grid within demand-charge headroom until BESS is restored.' },
  'GRID:brownout':        { peak: { 'ev:gridLoad': 98, 'ev:loadHeadroom': 2, 'ev:bessPower': 90, 'ev:bessSoc': 35, 'ev:chargingPower': 90 }, kwDown: 360, stationsDown: 2, faulted: 4, preventable: 0.4, onset: 4, peak: 18, rec: 'Ride through on BESS + solar; curtail DC-fast to protect the site.' },
  'GRID:supply_loss':     { peak: { 'ev:gridLoad': 18, 'ev:sessionsActive': 0, 'ev:chargingPower': 0, 'ev:bessPower': 100, 'ev:bessSoc': 25, 'ev:loadHeadroom': 40 }, kwDown: 600, stationsDown: 3, faulted: 10, preventable: 0.3, onset: 2, peak: 10, rec: 'Island the site on BESS + solar; prioritise AC bays; sequence restart on supply return.' },
}
const getSpec = (a, f) => SPEC[`${a}:${f}`] || SPEC['TX-1:overload']

const DUR = 90
function envAt(t, onset, peak, recStart) {
  if (t <= 0) return 0
  if (t < onset) return 0.3 * (t / onset)
  if (t < peak) return 0.3 + 0.7 * ((t - onset) / (peak - onset))
  if (t < recStart) return 1
  return Math.max(0, 1 - Math.min(1, (t - recStart) / 24))   // slower recovery — stays visible
}

export function buildScenario(assetId, faultId, { readiness = 55 } = {}) {
  const spec = getSpec(assetId, faultId)
  const asset = MODEL.assets.find(a => a.id === assetId) || { id: assetId, name: assetId }
  const contain = readiness / 100
  // Visuals barely dampen with readiness (the fault still visibly happens); the OUTCOME
  // ($, chargers down, recovery speed) is what a prepared response actually reduces.
  const visDamp = 1 - spec.preventable * contain * 0.3
  const outSev = 1 - spec.preventable * contain
  const recStart = spec.peak + Math.round(14 + (1 - contain) * 45)   // high readiness recovers; low readiness stays down
  const cost = MODEL.cost
  const lerp = (a, b, e) => a + (b - a) * e

  let revenueLost = 0, slaPenalty = 0, kwh = 0, sessions = 0, prevFaulted = 0
  const steps = []
  for (let t = 0; t <= DUR; t++) {
    const e = envAt(t, spec.onset, spec.peak, recStart)
    const vEff = e * visDamp
    const oEff = e * outSev
    const live = { ...HEALTHY }
    for (const k in spec.peak) live[k] = Math.round(lerp(HEALTHY[k] ?? 0, spec.peak[k], vEff))
    const faulted = Math.round((spec.faulted || 0) * oEff)
    live['ev:faultedChargers'] = faulted

    const kwDown = spec.kwDown * oEff
    revenueLost += kwDown * (1 / 60) * cost.rev_inr_per_kwh
    slaPenalty += spec.stationsDown * oEff * (1 / 60) * cost.penalty_inr_per_hour_down
    kwh += kwDown * (1 / 60)
    if (faulted > prevFaulted) sessions += faulted - prevFaulted
    prevFaulted = faulted

    const events = []
    if (t === spec.onset) events.push({ t, kind: 'warn', msg: `${asset.name} stressed — ${FAULTS[faultId]?.label || faultId} developing` })
    if (t === spec.peak) events.push({ t, kind: 'crit', msg: `${asset.name} faulted — ${spec.faulted || 0} charger(s) down, load rerouting` })
    if (t === recStart) events.push({ t, kind: contain >= 0.5 ? 'ok' : 'warn', msg: contain >= 0.5 ? 'Response containing the fault — recovery beginning' : 'Recovery beginning (response was slow)' })
    if (t === Math.min(DUR, recStart + 18)) events.push({ t, kind: 'ok', msg: `${asset.name} restored` })

    steps.push({
      t, live, overload: live['ev:gridLoad'] >= 95,
      metrics: { revenueLost: Math.round(revenueLost), slaPenalty: Math.round(slaPenalty), kwh: Math.round(kwh), sessions, faulted },
      events,
    })
  }

  // live operator narration — fires the first time each threshold is crossed
  const narration = []; const seen = {}
  const cue = (k, t, text) => { if (!seen[k]) { seen[k] = true; narration.push({ t, text }) } }
  for (const s of steps) {
    const L = s.live
    if (L['ev:gridLoad'] >= 85) cue('stress', s.t, `${asset.name} load is climbing past safe limits.`)
    if (L['ev:gridLoad'] >= 95) cue('crit', s.t, `Transformer overloaded — protection relay at risk.`)
    if (L['ev:thermalRunawayRisk'] >= 40) cue('runaway', s.t, `BESS thermal-runaway risk rising — isolate the pack.`)
    if (L['ev:faultedChargers'] > 0) cue('fault', s.t, `${L['ev:faultedChargers']} charger(s) dropping offline — sessions interrupted.`)
    if (L['ev:bessPower'] >= 80) cue('bess', s.t, `BESS is now supporting the site load.`)
    if (s.metrics.revenueLost > 0) cue('rev', s.t, `Revenue loss has begun accruing.`)
  }
  cue('recover', recStart, `Load rerouted — recovery beginning.`)
  narration.sort((a, b) => a.t - b.t)

  const facts = {
    site: MODEL.site, asset: asset.name, assetId, fault: FAULTS[faultId]?.label || faultId,
    peak_grid_load_pct: Math.max(...steps.map(s => s.live['ev:gridLoad'])),
    chargers_down: spec.faulted || 0, stations_affected: spec.stationsDown, sessions_dropped: sessions,
    kwh_curtailed: Math.round(kwh), revenue_lost_inr: Math.round(revenueLost), sla_penalty_inr: Math.round(slaPenalty),
    total_exposure_inr: Math.round(revenueLost + slaPenalty),
    preventable_pct: Math.round(spec.preventable * 100), response_readiness_pct: readiness,
    recommended_action: spec.rec, tariff_inr_per_kwh: cost.rev_inr_per_kwh, sla_penalty_inr_per_hour: cost.penalty_inr_per_hour_down,
  }
  return { title: `${asset.name} — ${FAULTS[faultId]?.label || faultId}`, steps, facts, narration, duration: DUR }
}

export function inr(v) {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)}Cr`
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)}L`
  if (v >= 1e3) return `₹${(v / 1e3).toFixed(0)}k`
  return `₹${Math.round(v)}`
}
