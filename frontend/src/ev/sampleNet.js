// sampleNet.js — a grounded EV charging network derived from data-layer/sample-network.json,
// shaped for the ported twin visual components. This is the demo network (a "network like
// yours") until a real operator export is imported via the data layer.

// 24h load curve: demand peaks in the evening, solar midday, transformer capacity 630 kW.
function buildCurve() {
  const cap = 630
  const out = []
  for (let h = 0; h < 24; h++) {
    const evening = Math.exp(-((h - 19) ** 2) / 8) * 560      // evening charging peak
    const morning = Math.exp(-((h - 9) ** 2) / 10) * 240
    const base = 90
    const demand = Math.round(base + evening + morning)
    const solar = Math.round(Math.max(0, Math.exp(-((h - 12.5) ** 2) / 9) * 320))
    const grid = Math.max(0, demand - solar)
    out.push({ hour: h, demand_kw: demand, solar_kw: solar, grid_kw: grid, capacity_kw: cap, dr_event: h >= 18 && h <= 21 })
  }
  return out
}

export const sampleNet = {
  grid: { transformer_rated_kw: 630, load_kw: 415 },
  cost: { rev_inr_per_kwh: 18, penalty_inr_per_hour_down: 1200, avg_session_kwh: 25 },
  stations: [
    { id: 'ST-01', name: 'Mall Plaza',  x: 28, y: 30, status: 'ok',      feeder: 'F-1', chargers_total: 2, chargers_available: 1, chargers_active: 1, chargers_faulted: 0, load_kw: 120, max_kw: 240, utilisation: 62 },
    { id: 'ST-02', name: 'Highway Hub', x: 72, y: 33, status: 'warning', feeder: 'F-1', chargers_total: 1, chargers_available: 0, chargers_active: 1, chargers_faulted: 0, load_kw: 210, max_kw: 240, utilisation: 88 },
    { id: 'ST-03', name: 'Depot AC',    x: 50, y: 78, status: 'ok',      feeder: 'F-2', chargers_total: 1, chargers_available: 0, chargers_active: 1, chargers_faulted: 0, load_kw: 20,  max_kw: 22,  utilisation: 45 },
  ],
  load_curve: buildCurve(),
}
