// analysis.js — the investment comparison, shared by the Decision Studio and Reports so
// there's one source of truth for "what does readiness buy you".
import { api } from './api.js'
import { computeImpact, exposureAt, money, pct } from './impact.js'
import { costOf } from './assumptions.js'

// Investment options — named strategies mapped to the engine's readiness lever, each with
// a cost. The Decision Explorer runs & ranks them.
export const LEVELS = [
  { key: 'none', name: 'Do nothing', readiness: 30, cost: 0 },
  { key: 'cross', name: 'Cross-train existing staff', readiness: 60, cost: 60_000 },
  { key: 'std', name: 'Hire + standard training', readiness: 78, cost: 130_000 },
  { key: 'full', name: 'Full readiness program', readiness: 95, cost: 240_000 },
]

export const stars = (roi) => roi >= 8 ? 5 : roi >= 4 ? 4 : roi >= 2 ? 3 : roi >= 1 ? 2 : 1

// One shared exposure model → success% and $ always move together (see impact.exposureAt).
export async function compareInvestments(scenario, domain) {
  const runs = await Promise.all(LEVELS.map(l => api.runGraph(scenario.id, domain, l.readiness)))
  const base = computeImpact(runs[0])
  const full = base.moneyTotal, prevPot = base.moneyPrev
  const rows = LEVELS.map((l, i) => {
    const contain = runs[i].nodes?.[0]?.result?.kpis?.containment_rate ?? 0
    const exposure = exposureAt(full, prevPot, contain)
    const saved = Math.max(0, full - exposure)
    const cost = costOf(l.key)
    return { ...l, cost, graph: runs[i], contain, exposure, saved, roi: cost > 0 && saved > 0 ? saved / cost : null }
  })
  const ranked = rows.filter(r => r.cost > 0 && r.roi).sort((a, b) => b.roi - a.roi)
  const best = ranked[0] || null
  return { rows, ranked, full, prevPot, worst: rows[0], best }
}

// Rule-based executive summary — no AI. Turns the run into a paragraph a COO can read.
export function execSummary({ scenario, domainName, cmp }) {
  const p = cmp.full > 0 ? Math.round(100 * cmp.prevPot / cmp.full) : 0
  const path = criticalPath(cmp.worst.graph)
  const rec = cmp.best
  const action = rec
    ? `Recommended action: ${rec.name} — an estimated ${money(rec.cost)} to avoid ${money(rec.saved)} (${rec.roi.toFixed(1)}× return).`
    : `This exposure is largely inherent to the fault; readiness investment yields limited return, so hold spend and monitor.`
  return `Under a ${scenario.name.toLowerCase()} in ${domainName} operations, unmitigated exposure is estimated at ${money(cmp.full)}, of which ${money(cmp.prevPot)} (${p}%) is avoidable through operator readiness. The critical path runs ${path}. ${action}`
}

// The dominant chain through the cascade — root then its deepest line of consequences.
export function criticalPath(rg) {
  if (!rg?.nodes?.length) return '—'
  const byId = Object.fromEntries(rg.nodes.map(n => [n.run_id, n]))
  const kids = {}
  ;(rg.edges || []).forEach(e => { (kids[e.parent_run_id] = kids[e.parent_run_id] || []).push(e.child_run_id) })
  const names = []
  let cur = rg.nodes[0].run_id, guard = 0
  while (cur && guard++ < 8) {
    names.push(byId[cur]?.scenario_name || '')
    cur = (kids[cur] || [])[0]
  }
  return names.filter(Boolean).slice(0, 4).join(' → ')
}
