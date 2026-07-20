// cascade.js — the animated fault cascade for the EV network. Deterministic timeline built
// from the topology (which stations sit on the faulted feeder) + the real tariff/SLA costs.
// Everything ($ lost, SLA penalty, kWh curtailed) is a real formula, not a scripted number.
//
// Fault modelled: peak-load transformer overload on TX-1 → Feeder F-1 overcurrent trip.
// ST-02 (highest utilisation) is the INHERENT casualty; ST-01 is PREVENTABLE — a prepared
// response (high readiness) contains it. ST-03 sits on F-2 and is unaffected.

const DUR = 120                 // simulated steps; each step ≈ 1 minute of a real incident

export function buildTimeline(net, { readiness = 55 } = {}) {
  const base = net.stations
  const cost = net.cost
  const cap = net.grid.transformer_rated_kw
  const contain = readiness / 100
  const st01Saved = contain >= 0.6
  const tRecover = st01Saved ? 64 : 104

  const sched = {
    'ST-02': { warn: 16, crit: 22, recover: tRecover },
    'ST-01': st01Saved ? { warn: 32, crit: null, recover: 56 } : { warn: 32, crit: 40, recover: tRecover },
  }
  const statusAt = (id, t) => {
    const sc = sched[id]; if (!sc) return 'ok'
    if (sc.crit != null && t >= sc.crit && t < sc.recover) return 'critical'
    if (sc.recover != null && t >= sc.recover && t < sc.recover + 12) return 'warning'   // recovering
    if (t >= sc.warn && (sc.crit == null ? t < sc.warn + 22 : t < sc.crit)) return 'warning'
    return 'ok'
  }

  let revenueLost = 0, slaPenalty = 0, kwh = 0, sessions = 0
  const prev = {}
  const steps = []

  for (let t = 0; t <= DUR; t++) {
    const stations = base.map(s => {
      const st = statusAt(s.id, t)
      return {
        ...s, status: st,
        chargers_faulted: st === 'critical' ? s.chargers_total : 0,
        chargers_active: st === 'critical' ? 0 : s.chargers_active,
        chargers_available: st === 'critical' ? 0 : s.chargers_available,
        load_kw: st === 'critical' ? 0 : s.load_kw,
      }
    })
    const crit = stations.filter(s => s.status === 'critical')
    const kwDown = crit.reduce((a, s) => a + (base.find(b => b.id === s.id).load_kw), 0)

    // real formulas: ₹ = kWh × tariff; SLA = ₹/hr × stations-down × hours
    revenueLost += kwDown * (1 / 60) * cost.rev_inr_per_kwh
    slaPenalty += crit.length * (1 / 60) * cost.penalty_inr_per_hour_down
    kwh += kwDown * (1 / 60)

    const events = []
    stations.forEach(s => {
      if (prev[s.id] !== s.status) {
        const b = base.find(x => x.id === s.id)
        if (s.status === 'critical') { sessions += b.chargers_active; events.push({ t, kind: 'crit', msg: `${s.name} tripped — ${b.chargers_active} session(s) dropped` }) }
        else if (s.status === 'warning' && prev[s.id] === 'ok') events.push({ t, kind: 'warn', msg: `${s.name} at risk — feeder F-1 overloaded` })
        else if (s.status === 'ok' && prev[s.id]) events.push({ t, kind: 'ok', msg: `${s.name} recovered` })
        prev[s.id] = s.status
      }
    })
    if (t === 6) events.push({ t, kind: 'warn', msg: 'TX-1 overloaded — demand exceeds transformer capacity' })

    // grid load: climbs into overload, then drops as stations trip offline
    const rise = Math.min(1, t / 20)
    let load = 415 + rise * (cap * 1.06 - 415)
    load = Math.max(120, load - kwDown)

    steps.push({
      t, stations, grid: { ...net.grid, load_kw: Math.round(load) },
      overload: load > cap,
      metrics: { revenueLost: Math.round(revenueLost), slaPenalty: Math.round(slaPenalty), kwh: Math.round(kwh), sessions, criticalNow: crit.length },
      events,
    })
  }
  return { steps, duration: DUR, st01Saved }
}

// Indian-style short currency
export function inr(v) {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)}Cr`
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)}L`
  if (v >= 1e3) return `₹${(v / 1e3).toFixed(0)}k`
  return `₹${Math.round(v)}`
}
