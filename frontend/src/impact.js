import { moneyRate } from './assumptions.js'
// impact.js — pure helpers shared by the modes: cascade layout, the estimated cost model,
// and the "which asset is critical" reducer. No React, no fetch — just math on the graph
// the engine returned.

// ── cascade layout (longest-path layering over the DAG) ──────────────────────────
export const NODE_W = 152
export const NODE_H = 54
const COL_GAP = 188
const ROW_GAP = 66
const MX = 16
const MY = 18

export function layoutGraph(rg) {
  if (!rg || !rg.nodes) return { nodes: [], edges: [], w: 400, h: 120 }
  const ids = rg.nodes.map(n => n.run_id)
  const indeg = {}, adj = {}, depth = {}
  ids.forEach(i => { indeg[i] = 0; adj[i] = []; depth[i] = 0 })
  rg.edges.forEach(e => {
    if (adj[e.parent_run_id] == null || indeg[e.child_run_id] == null) return
    indeg[e.child_run_id]++; adj[e.parent_run_id].push(e.child_run_id)
  })
  const deg = { ...indeg }
  const q = ids.filter(i => !deg[i]); const order = []
  while (q.length) { const id = q.shift(); order.push(id); adj[id].forEach(to => { if (--deg[to] === 0) q.push(to) }) }
  ids.forEach(i => { if (!order.includes(i)) order.push(i) })
  order.forEach(id => adj[id].forEach(to => { depth[to] = Math.max(depth[to], depth[id] + 1) }))

  const cols = {}
  rg.nodes.forEach(n => { const d = depth[n.run_id] || 0; (cols[d] = cols[d] || []).push(n) })
  const maxRows = Math.max(1, ...Object.values(cols).map(c => c.length))
  const nodes = []
  Object.keys(cols).map(Number).forEach(d => {
    const col = cols[d]; const off = (maxRows - col.length) / 2
    col.forEach((n, i) => {
      nodes.push({
        id: n.run_id, x: MX + d * COL_GAP, y: MY + (i + off) * ROW_GAP,
        label: n.scenario_name, kind: n.node_kind, impact: n.impact_level, category: n.category,
      })
    })
  })
  const pos = Object.fromEntries(nodes.map(n => [n.id, n]))
  const edges = rg.edges
    .map(e => ({ a: pos[e.parent_run_id], b: pos[e.child_run_id], preventable: e.preventable, condition: e.condition }))
    .filter(e => e.a && e.b)
  const w = Math.max(360, ...nodes.map(n => n.x + NODE_W + MX))
  const h = Math.max(120, ...nodes.map(n => n.y + NODE_H + MY))
  return { nodes, edges, w, h }
}

// ── estimated cost model (same coefficients as the Hub) ──────────────────────────
const IMPACT_W = { low: 0.4, medium: 1, high: 2.2, critical: 4 }
const wOf = (impact) => IMPACT_W[impact] ?? 1
const MODEL = {
  railway: { money: 3.0e5, units: (W) => [{ label: 'passenger-minutes delayed', value: Math.round(W * 52000) }, { label: 'trains held', value: Math.max(1, Math.round(W * 1.1)) }] },
  hospital: { money: 1.5e5, units: (W) => [{ label: 'surgeries cancelled', value: Math.max(1, Math.round(W * 1.4)) }, { label: 'patients affected', value: Math.round(W * 130) }] },
  aerospace: { money: 4.0e5, units: (W) => [{ label: 'flights delayed', value: Math.max(1, Math.round(W * 2.2)) }, { label: 'hours AOG', value: Math.round(W * 3.5) }] },
  defence: { money: 1.8e5, units: (W) => [{ label: 'min response delay', value: Math.round(W * 22) }, { label: 'readiness', value: Math.round(W * 6), suffix: '%', neg: true }] },
  ev: { money: 2.5e5, units: (W) => [{ label: 'charging sessions lost', value: Math.round(W * 180) }, { label: 'MWh curtailed', value: Math.round(W * 2.4) }] },
}
const DEFAULT_MODEL = { money: 2.0e5, units: (W) => [{ label: 'impact units', value: Math.round(W * 100) }] }

export function computeImpact(rg) {
  const m = MODEL[rg?.domain] || DEFAULT_MODEL
  const nodes = rg?.nodes || []
  const Wtotal = nodes.reduce((a, n) => a + wOf(n.impact_level), 0)
  const prevIds = new Set((rg?.edges || []).filter(e => e.preventable).map(e => e.child_run_id))
  const Wprev = nodes.filter(n => prevIds.has(n.run_id)).reduce((a, n) => a + wOf(n.impact_level), 0)
  return {
    moneyTotal: moneyRate(rg?.domain) * Wtotal,
    moneyPrev: moneyRate(rg?.domain) * Wprev,
    moneyFloor: moneyRate(rg?.domain) * (Wtotal - Wprev),   // what you're left with even if contained
    prevPct: Wtotal ? Math.round((100 * Wprev) / Wtotal) : 0,
    units: m.units(Wtotal),
    hasPreventable: Wprev > 1e-6,
  }
}

// ── explainability: where the exposure comes from, by cause/category ─────────────
export function exposureByCategory(rg) {
  const mMoney = moneyRate(rg?.domain)
  const acc = {}
  ;(rg?.nodes || []).forEach(n => { acc[n.category || 'other'] = (acc[n.category || 'other'] || 0) + mMoney * wOf(n.impact_level) })
  const total = Object.values(acc).reduce((a, b) => a + b, 0) || 1
  return Object.entries(acc)
    .map(([category, value]) => ({ category, value, pct: Math.round(100 * value / total) }))
    .sort((a, b) => b.value - a.value)
}

// ── one exposure model everyone shares ───────────────────────────────────────────
// Exposure ALWAYS falls as containment rises, so success% and $ never contradict.
// Scenarios with a preventable branch save more; even a fully-inherent fault saves ~15%
// from a faster response. full = uncontained cost, prevPot = the avoidable slice.
export function savingFactor(full, prevPot) { return Math.min(0.7, 0.15 + (full > 0 ? prevPot / full : 0)) }
export function exposureAt(full, prevPot, containment) { return full * (1 - savingFactor(full, prevPot) * (containment || 0)) }
export function nodeExposure(domain, impact) { return moneyRate(domain) * (IMPACT_W[impact] ?? 1) }

// ── twin view: rank assets/nodes by how much sits downstream of them ─────────────
export function criticality(rg) {
  const nodes = rg?.nodes || []
  const kids = {}
  ;(rg?.edges || []).forEach(e => { (kids[e.parent_run_id] = kids[e.parent_run_id] || []).push(e.child_run_id) })
  const reach = (id, seen = new Set()) => {
    ;(kids[id] || []).forEach(c => { if (!seen.has(c)) { seen.add(c); reach(c, seen) } })
    return seen
  }
  return nodes.map(n => ({
    name: n.scenario_name, kind: n.node_kind, impact: n.impact_level,
    downstream: reach(n.run_id).size,
  })).sort((a, b) => b.downstream - a.downstream || wOf(b.impact) - wOf(a.impact))
}

// ── formatting ───────────────────────────────────────────────────────────────────
export function money(v) {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${Math.round(v / 1e3)}k`
  return `$${Math.round(v)}`
}
export function num(v) {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(v >= 1e4 ? 0 : 1)}k`
  return `${Math.round(v)}`
}
export const pct = (v) => `${Math.round((v || 0) * 100)}%`
