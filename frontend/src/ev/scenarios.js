// scenarios.js — the EV fault/cascade brain. For any (asset, fault) it produces a timeline of
// telemetry frames (which drive the 3-D twin) AND a structured facts object (which grounds the
// AI copilot). Every ₹ is a real formula (kWh × tariff, station-hours × SLA), never scripted.
import { MODEL, FAULTS } from './networkModel.js'

export const HEALTHY = {
  'ev:gridLoad': 66, 'ev:transformerTemp': 58, 'ev:loadHeadroom': 34, 'ev:peakDemand': 415,
  'ev:bessSoc': 72, 'ev:bessPower': 40, 'ev:solarOutput': 120, 'ev:sessionsActive': 6,
  'ev:faultedChargers': 0, 'ev:thermalRunawayRisk': 4, 'ev:cellTempMax': 31, 'ev:chargingPower': 180,
}

// Time Machine — EV-adoption demand growth + infrastructure ageing (BESS capacity fade).
export const HORIZONS = {
  now: { label: 'Now', demand: 1.0, degrade: 1.0 },
  h27: { label: '2027', demand: 1.3, degrade: 0.94 },
  h30: { label: '2030', demand: 1.7, degrade: 0.86 },
  h35: { label: '2035', demand: 2.2, degrade: 0.75 },
}

// Operating conditions — each worsens the fault (modelled as a hit to effective readiness).
export const CONDITIONS = [
  { id: 'peak', label: '⚡ Peak load', pen: 15 },
  { id: 'heatwave', label: '🔥 Heatwave', pen: 18 },
  { id: 'rain', label: '🌧 Heavy rain', pen: 8 },
]

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

// ordered cascade — each stage lights an asset red + pops a numbered bubble above it.
// `at` is the fraction of the timeline; `anchor` maps to a 3-D asset in the twin.
const SEQ = {
  'TX-1:overload': [{ at: 0.16, anchor: 'transformer', label: 'Transformer T1 overloads' }, { at: 0.34, anchor: 'dcfc', label: 'DC chargers trip offline' }, { at: 0.52, anchor: 'ems', label: 'EMS sheds non-critical load' }, { at: 0.70, anchor: 'building', label: 'Mall supply curtailed' }],
  'TX-1:overheat': [{ at: 0.20, anchor: 'transformer', label: 'Transformer overheating' }, { at: 0.42, anchor: 'dcfc', label: 'DC-fast power throttled' }, { at: 0.64, anchor: 'ems', label: 'EMS derates the site' }],
  'F-1:overcurrent_trip': [{ at: 0.14, anchor: 'transformer', label: 'Feeder F-1 overcurrent' }, { at: 0.32, anchor: 'dcfc', label: 'DC bank trips offline' }, { at: 0.55, anchor: 'ems', label: 'Load rerouted to F-2' }],
  'F-2:overcurrent_trip': [{ at: 0.14, anchor: 'ems', label: 'Feeder F-2 overcurrent' }, { at: 0.36, anchor: 'dcfc', label: 'AC bays drop offline' }],
  'DCFC:charger_offline': [{ at: 0.12, anchor: 'dcfc', label: 'DC chargers go offline' }, { at: 0.42, anchor: 'ems', label: 'Sessions rerouted' }],
  'DCFC:connector_fault': [{ at: 0.12, anchor: 'dcfc', label: 'Connector fault detected' }, { at: 0.40, anchor: 'dcfc', label: 'Bay locked out' }],
  'BESS-A:thermal_runaway': [{ at: 0.16, anchor: 'bess', label: 'BESS thermal-runaway risk' }, { at: 0.36, anchor: 'bess', label: 'Pack isolated' }, { at: 0.56, anchor: 'transformer', label: 'Grid must cover the load' }, { at: 0.74, anchor: 'ems', label: 'Demand-charge spike' }],
  'BESS-A:offline': [{ at: 0.16, anchor: 'bess', label: 'BESS goes offline' }, { at: 0.42, anchor: 'transformer', label: 'Grid carries the peak' }],
  'GRID:brownout': [{ at: 0.12, anchor: 'grid', label: 'Grid brownout' }, { at: 0.32, anchor: 'bess', label: 'BESS + solar ride-through' }, { at: 0.54, anchor: 'dcfc', label: 'DC-fast curtailed' }],
  'GRID:supply_loss': [{ at: 0.10, anchor: 'grid', label: 'Grid supply lost' }, { at: 0.28, anchor: 'bess', label: 'Site islands on BESS' }, { at: 0.48, anchor: 'dcfc', label: 'DC chargers shut down' }, { at: 0.70, anchor: 'building', label: 'Mall on backup only' }],
}
const getSeq = (a, f) => SEQ[`${a}:${f}`] || SEQ['TX-1:overload']

// Fault-specific mitigation strategies. readiness = how much the response contains the fault
// (drives exposure + how far the cascade spreads). Every set leads with a "do nothing" baseline.
const STRATS = {
  'TX-1:overload': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'No intervention — ride it out.' },
    { key: 'shed', name: 'Shed non-critical DC load', readiness: 70, mech: 'Drop low-priority DC sessions to hold TX-1 under 90%.' },
    { key: 'bess', name: 'Dispatch BESS', readiness: 84, mech: 'Discharge BESS-A to cover peak and protect the transformer.' },
    { key: 'curtail', name: 'Curtail charging 50%', readiness: 62, mech: 'Halve DC-fast power site-wide during the peak window.' },
  ],
  'TX-1:overheat': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Let the transformer keep heating.' },
    { key: 'cool', name: 'Force-cool + throttle', readiness: 78, mech: 'Run forced cooling and throttle DC power before it derates.' },
    { key: 'shift', name: 'Shift load to Feeder F-2', readiness: 60, mech: 'Move DC-bank load onto Feeder F-2 headroom.' },
  ],
  'F-1:overcurrent_trip': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Leave the feeder tripped.' },
    { key: 'reclose', name: 'Re-close after load-shed', readiness: 72, mech: 'Shed load, then re-close Feeder F-1.' },
    { key: 'rebal', name: 'Rebalance to F-2', readiness: 80, mech: 'Move the DC bank onto Feeder F-2 and restore charging.' },
  ],
  'F-2:overcurrent_trip': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Leave the feeder tripped.' },
    { key: 'shift', name: 'Shift AC bays to F-1', readiness: 74, mech: 'Move AC bays onto Feeder F-1 headroom and re-close.' },
    { key: 'stagger', name: 'Stagger AC charging', readiness: 60, mech: 'Sequence AC sessions to stay under the feeder limit.' },
  ],
  'DCFC:charger_offline': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Leave the chargers offline.' },
    { key: 'reboot', name: 'Remote-reboot OCPP', readiness: 82, mech: 'Restart the OCPP session controller remotely.' },
    { key: 'reroute', name: 'Reroute drivers', readiness: 66, mech: 'Send arriving drivers to the working bays.' },
    { key: 'truck', name: 'Dispatch truck-roll', readiness: 55, mech: 'Send a technician if the reboot fails.' },
  ],
  'DCFC:connector_fault': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Leave the connector faulted.' },
    { key: 'lock', name: 'Lock + reroute', readiness: 84, mech: 'Lock the faulted connector, route the driver to the next bay.' },
    { key: 'reset', name: 'Remote diagnostic reset', readiness: 68, mech: 'Attempt a remote reset of the connector.' },
  ],
  'BESS-A:thermal_runaway': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Let the pack keep heating — fire risk.' },
    { key: 'isolate', name: 'Isolate + cool pack', readiness: 86, mech: 'Isolate BESS-A and trigger the cooling/suppression system.' },
    { key: 'gridcov', name: 'Cover load from grid', readiness: 62, mech: 'Carry load from grid within the demand-charge cap while isolating.' },
  ],
  'BESS-A:offline': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Run without storage support.' },
    { key: 'hold', name: 'Hold peak on grid', readiness: 74, mech: 'Carry peak on grid within demand-charge headroom until BESS is back.' },
    { key: 'backup', name: 'Bring backup online', readiness: 80, mech: 'Start backup storage/genset to restore support.' },
  ],
  'GRID:brownout': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Ride the brownout unmanaged.' },
    { key: 'ride', name: 'Ride through on BESS + solar', readiness: 82, mech: 'Support the site from BESS-A and the solar canopy.' },
    { key: 'curtail', name: 'Curtail DC-fast', readiness: 66, mech: 'Cut DC-fast power to protect the site during the sag.' },
  ],
  'GRID:supply_loss': [
    { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'Full outage — no backup.' },
    { key: 'island', name: 'Island on BESS + solar', readiness: 80, mech: 'Disconnect and run the site islanded on BESS-A + solar.' },
    { key: 'priority', name: 'Prioritise AC bays', readiness: 60, mech: 'Keep AC bays up, shed DC-fast, sequence restart on return.' },
  ],
}
const DEFAULT_STRATS = [
  { key: 'nothing', name: 'Do nothing', readiness: 5, mech: 'No intervention — ride it out.' },
  { key: 'bess', name: 'Activate BESS', readiness: 80, mech: 'Dispatch on-site storage to cover load.' },
  { key: 'reroute', name: 'Reroute demand', readiness: 58, mech: 'Send arriving EVs elsewhere to cut demand.' },
  { key: 'curtail', name: 'Curtail charging', readiness: 66, mech: 'Throttle charging power to contain the fault.' },
]
export const strategiesFor = (assetId, faultId) => STRATS[`${assetId}:${faultId}`] || DEFAULT_STRATS

const DUR = 90
function envAt(t, onset, peak, recStart) {
  if (t <= 0) return 0
  if (t < onset) return 0.3 * (t / onset)
  if (t < peak) return 0.3 + 0.7 * ((t - onset) / (peak - onset))
  if (t < recStart) return 1
  return Math.max(0, 1 - Math.min(1, (t - recStart) / 24))   // slower recovery — stays visible
}

export function buildScenario(assetId, faultId, { readiness = 55, horizon = 'now', conditions = [] } = {}) {
  const spec = getSpec(assetId, faultId)
  const asset = MODEL.assets.find(a => a.id === assetId) || { id: assetId, name: assetId }
  const h = HORIZONS[horizon] || HORIZONS.now
  const dem = h.demand
  const preventable = spec.preventable * h.degrade   // aged infra is harder to contain
  const condPen = conditions.reduce((a, c) => a + (CONDITIONS.find(x => x.id === c)?.pen || 0), 0)
  const readinessEff = Math.max(0, readiness - condPen)   // conditions eat into the response
  const contain = readinessEff / 100
  const seq = getSeq(assetId, faultId)
  // a prepared response contains the cascade earlier → fewer stages actually fire
  const stagesFired = readinessEff >= 85 ? 1 : readinessEff >= 65 ? 2 : readinessEff >= 42 ? Math.max(2, seq.length - 1) : seq.length
  // Visuals barely dampen with readiness (the fault still visibly happens); the OUTCOME
  // ($, chargers down, recovery speed) is what a prepared response actually reduces.
  const visDamp = 1 - preventable * contain * 0.3
  const outSev = 1 - preventable * contain
  const recStart = spec.peak + Math.round(14 + (1 - contain) * 45)   // high readiness recovers; low readiness stays down
  const cost = MODEL.cost
  const lerp = (a, b, e) => a + (b - a) * e
  // horizon-aged baseline: demand growth lifts idle load and cuts headroom
  const base = {
    ...HEALTHY,
    'ev:gridLoad': Math.min(90, Math.round(66 + (dem - 1) * 22)),
    'ev:loadHeadroom': Math.max(6, Math.round(34 - (dem - 1) * 24)),
    'ev:peakDemand': Math.round(HEALTHY['ev:peakDemand'] * dem),
    'ev:sessionsActive': Math.round(HEALTHY['ev:sessionsActive'] * Math.min(2, dem)),
    'ev:chargingPower': Math.round(HEALTHY['ev:chargingPower'] * dem),
  }
  if (conditions.includes('heatwave')) { base['ev:transformerTemp'] += 12; base['ev:cellTempMax'] += 8 }
  if (conditions.includes('rain')) base['ev:solarOutput'] = Math.round(base['ev:solarOutput'] * 0.4)

  let revenueLost = 0, slaPenalty = 0, kwh = 0, sessions = 0, prevFaulted = 0
  const steps = []
  for (let t = 0; t <= DUR; t++) {
    const e = envAt(t, spec.onset, spec.peak, recStart)
    const vEff = e * visDamp
    const oEff = e * outSev
    const live = { ...base }
    for (const k in spec.peak) live[k] = Math.round(lerp(base[k] ?? 0, spec.peak[k], vEff))
    const faulted = Math.round((spec.faulted || 0) * oEff)
    live['ev:faultedChargers'] = faulted

    const kwDown = spec.kwDown * oEff * dem
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
    site: MODEL.site, horizon: h.label, asset: asset.name, assetId, fault: FAULTS[faultId]?.label || faultId,
    peak_grid_load_pct: Math.max(...steps.map(s => s.live['ev:gridLoad'])),
    chargers_down: spec.faulted || 0, stations_affected: spec.stationsDown, sessions_dropped: sessions,
    kwh_curtailed: Math.round(kwh), revenue_lost_inr: Math.round(revenueLost), sla_penalty_inr: Math.round(slaPenalty),
    total_exposure_inr: Math.round(revenueLost + slaPenalty),
    preventable_pct: Math.round(preventable * 100), response_readiness_pct: readinessEff,
    conditions: conditions.map(c => CONDITIONS.find(x => x.id === c)?.label || c),
    recommended_action: spec.rec, tariff_inr_per_kwh: cost.rev_inr_per_kwh, sla_penalty_inr_per_hour: cost.penalty_inr_per_hour_down,
  }
  return { title: `${asset.name} — ${FAULTS[faultId]?.label || faultId}`, steps, facts, narration, sequence: seq, stagesFired, duration: DUR }
}

export function inr(v) {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)}Cr`
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)}L`
  if (v >= 1e3) return `₹${(v / 1e3).toFixed(0)}k`
  return `₹${Math.round(v)}`
}

function seededFrac(...parts) {
  let hsh = 2166136261
  const s = parts.join('|')
  for (let i = 0; i < s.length; i++) { hsh ^= s.charCodeAt(i); hsh = Math.imul(hsh, 16777619) }
  return ((hsh >>> 0) % 100000) / 100000
}

// Fault-specific Monte Carlo — 120 replays at random readiness; containment is shaped by the
// fault's own preventable share, so every fault gets a genuinely different distribution.
export function buildMonteCarlo(assetId, faultId, N = 120) {
  const spec = getSpec(assetId, faultId)
  const prev = spec.preventable
  const samples = []
  let certified = 0, sum = 0
  for (let i = 0; i < N; i++) {
    const r = seededFrac(assetId, faultId, i)
    const noise = (seededFrac(faultId, i, 'n') - 0.5) * 0.1
    const c = Math.max(0, Math.min(1, prev * (0.15 + 0.85 * r) + noise))
    samples.push(c); sum += c; if (c >= 0.5) certified++
  }
  return { runs: N, samples, certified_pct: Math.round(100 * certified / N), contained_pct: Math.round(100 * sum / N) }
}
