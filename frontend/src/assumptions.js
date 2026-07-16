// The ONE place model assumptions live — the $ figures the simulation engine can't provide
// (it models physics/ops, not money). User-editable and saved to the browser, so nothing
// financial is baked into the code.
export const DEF = {
  money: { railway: 300000, hospital: 150000, aerospace: 400000, defence: 180000, default: 200000 },
  cost: { cross: 60000, std: 130000, full: 240000 },
}

export function getAssumptions() {
  try {
    const s = JSON.parse(localStorage.getItem('simcore_assumptions') || '{}')
    return { money: { ...DEF.money, ...(s.money || {}) }, cost: { ...DEF.cost, ...(s.cost || {}) } }
  } catch { return { money: { ...DEF.money }, cost: { ...DEF.cost } } }
}
export function saveAssumptions(a) { localStorage.setItem('simcore_assumptions', JSON.stringify(a)) }
export function resetAssumptions() { localStorage.removeItem('simcore_assumptions') }
export function moneyRate(domain) { const a = getAssumptions(); return a.money[domain] ?? a.money.default }
export function costOf(key) { const a = getAssumptions(); return a.cost[key] || 0 }
